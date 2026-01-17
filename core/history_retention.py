from __future__ import annotations

import json
import os
import tempfile
import time
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("montrix.history_retention")

_DEFAULT_TTL_S = 5.0
_cache: Dict[str, Any] = {"ts": 0.0, "data": None}


def _load_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        logger.exception("history_retention: failed to load json: %s", path)
        return None

def load_history_retention_settings(settings_path: str = "runtime/settings.json") -> Dict[str, Any]:
    """
    Best-effort settings loader with tiny TTL cache.
    Returns dict like:
      {
        "trades_jsonl": {"max_lines": 5000}
      }
    """
    now = time.time()
    try:
        ts = float(_cache.get("ts") or 0.0)
    except Exception:
        ts = 0.0

    if (now - ts) < _DEFAULT_TTL_S and isinstance(_cache.get("data"), dict):
        return dict(_cache["data"])

    root = _load_json(settings_path) or {}
    hr = root.get("history_retention")
    if not isinstance(hr, dict):
        hr = {}

    _cache["ts"] = now
    _cache["data"] = dict(hr)
    return dict(hr)


def _atomic_write_text(path: str, text: str) -> None:
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)

    fd = None
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix="ret_", suffix=".tmp", dir=directory)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        fd = None
        os.replace(tmp_path, path)
        tmp_path = None
    except Exception as e:
        logger.debug("history_retention: atomic write failed for %s: %s", path, e)
    finally:
        if tmp_path is not None:
            try:
                os.remove(tmp_path)
            except Exception:
                logger.exception("history_retention: failed to remove tmp file: %s", tmp_path)
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                logger.exception("history_retention: failed to close fd")



def rotate_keep_last_lines(path: str, max_lines: int) -> bool:
    """
    Keep last max_lines lines in file at `path`.
    Returns True if rotation happened, else False.
    Never raises.
    """
    try:
        max_lines_i = int(max_lines)
    except Exception:
        logger.exception("history_retention: invalid max_lines=%r for %s", max_lines, path)
        return False

    if max_lines_i <= 0:
        return False

    try:
        if not os.path.exists(path):
            return False
    except Exception:
        logger.exception("history_retention: exists() check failed for %s", path)
        return False

    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        logger.exception("history_retention: failed to read file: %s", path)
        return False

    try:
        if len(lines) <= max_lines_i:
            return False
        trimmed = lines[-max_lines_i:]
        _atomic_write_text(path, "".join(trimmed))
        return True
    except Exception:
        logger.exception("history_retention: rotate failed for %s", path)
        return False


def apply_retention_for_key(file_path: str, key: str, settings_path: str = "runtime/settings.json") -> None:
    """
    key: "trades_jsonl" (health_log запрещён по POLICY-01)
    """
    try:
        hr = load_history_retention_settings(settings_path=settings_path)
        policy = hr.get(key)
        if key == "health_log":
            # POLICY-01: файловый health.log запрещён
            return
        if not isinstance(policy, dict):
            return
        ml = policy.get("max_lines")
        if ml is None:
            return
        rotate_keep_last_lines(file_path, int(ml))
    except Exception:
        logger.exception("history_retention: apply_retention failed for key=%s file=%s", key, file_path)
        return

