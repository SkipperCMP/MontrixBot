from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import os


from . import runtime_sanity
from .history_retention import apply_retention_for_key

ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = ROOT / "runtime"
DEFAULT_HEALTH_LOG = RUNTIME_DIR / "health.log"


ParsedLine = Tuple[str, str, str, str, str, str, Dict[str, str]]


def _parse_health_line(line: str) -> Optional[ParsedLine]:
    """
    Разбор одной строки health.log, с форматом как у scripts/health_monitor.py:

      2025-11-09 17:00:00 UTC | mode=REAL dry_run=True safe=ON | \
      trades=553B open=2 close=2 active=[] last_ts=...

    Возвращает:
      (ts, trades, open_, close, active, last_ts, flags)
    или None, если строка не соответствует формату.
    """
    line = (line or "").strip()
    if not line:
        return None

    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 3:
        return None

    ts = parts[0]
    right = parts[2]  # правая часть "trades=..., open=..., ..."
    kv: Dict[str, str] = {}
    for token in right.split():
        if "=" in token:
            k, v = token.split("=", 1)
            kv[k] = v

    trades = kv.get("trades", "?")
    open_ = kv.get("open", "?")
    close = kv.get("close", "?")
    active = kv.get("active", "?")
    last_ts = kv.get("last_ts", "?")

    mid = parts[1]  # средняя часть "mode=REAL dry_run=True safe=ON ..."
    flags: Dict[str, str] = {}
    for token in mid.split():
        if "=" in token:
            k, v = token.split("=", 1)
            flags[k] = v

    return ts, trades, open_, close, active, last_ts, flags


def load_health_snapshot(
    log_path: str | os.PathLike[str] | None = None,
    max_lines: int = 500,
) -> Dict[str, Any]:
    """
    Читает runtime/health.log (или заданный путь) и возвращает удобную структуру
    для UI-слоя.

    Возвращает dict:
    {
        "log_path": "<абсолютный путь>",
        "entries": [
            {
                "ts": ...,
                "trades": ...,
                "open": ...,
                "close": ...,
                "active": ...,
                "last_ts": ...,
                "flags": {...}
            },
            ...
        ],
        "last_flags": {...},
        "last_ts_str": "<последняя строка ts или None>",
    }
    """
    if log_path is None:
        path = DEFAULT_HEALTH_LOG
    else:
        path = Path(log_path)

    entries: List[Dict[str, Any]] = []
    last_flags: Dict[str, str] = {}
    last_ts_str: Optional[str] = None

    try:
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()[-max_lines:]

        # STEP1.4.4: log retention (best-effort). Trim file itself, not just UI slice.
        try:
            apply_retention_for_key(str(path), "health_log")
        except Exception:
            pass

    except FileNotFoundError:
        # health.log ещё не создан — возвращаем пустую структуру
        return {
            "log_path": str(path),
            "entries": [],
            "last_flags": {},
            "last_ts_str": None,
        }
    except Exception:
        # любые другие проблемы не должны ломать UI
        return {
            "log_path": str(path),
            "entries": [],
            "last_flags": {},
            "last_ts_str": None,
        }

    for ln in lines:
        parsed = _parse_health_line(ln)
        if not parsed:
            continue
        ts, trades, open_, close, active, last_ts, flags = parsed
        entries.append(
            {
                "ts": ts,
                "trades": trades,
                "open": open_,
                "close": close,
                "active": active,
                "last_ts": last_ts,
                "flags": flags,
            }
        )
        last_flags = flags
        last_ts_str = ts

    return {
        "log_path": str(path),
        "entries": entries,
        "last_flags": last_flags,
        "last_ts_str": last_ts_str,
    }

def get_runtime_sanity_report() -> Dict[str, Any]:
    """
    Обёртка над runtime_sanity.run_runtime_sanity_check().

    Держим её в health_api, чтобы UI/health-слой мог получать
    sanity-отчёт, не импортируя runtime_sanity напрямую.
    """
    try:
        return runtime_sanity.run_runtime_sanity_check()
    except Exception:
        import logging

        logger = logging.getLogger("montrix.health")
        logger.exception("health_api: runtime sanity check failed")
        return {
            "ok": False,
            "issues": ["runtime_sanity_failed"],
            "warnings": [],
            "summary": {},
        }
