# scripts/health_contract.py
"""
Health Contract (v2.2.104):
- Single snapshot to stdout (JSON)
- Exit codes:
    0 = OK
    2 = WARN
    4 = FAIL
Policy:
- Snapshot-only. Must not write health logs.
- Offline-safe. UI not required.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

# Allow running both:
#   python scripts/health_contract.py
#   python -m scripts.health_contract
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.health_api import get_health_snapshot_for_core


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_runtime_status() -> Dict[str, Any]:
    p = os.path.join("runtime", "status.json")
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"ok": False, "error": "runtime/status.json_missing"}
    except Exception as e:
        return {"ok": False, "error": f"runtime/status.json_read_failed:{e}"}


def _is_safe_hard_lock() -> bool:
    try:
        from tools.safe_lock import is_safe_on
        return bool(is_safe_on())
    except Exception:
        return False


def _evaluate(snap: Dict[str, Any], status: Dict[str, Any], safe_lock: bool) -> Tuple[str, int, list[str]]:
    """
    Returns (level, exit_code, reasons)
    """
    reasons: list[str] = []

    sanity = snap.get("sanity") or {}
    sanity_ok = bool(sanity.get("ok", False))
    issues = sanity.get("issues") or []
    warnings = sanity.get("warnings") or []

    if not sanity_ok:
        reasons.append("SANITY_FAIL")
        if issues:
            reasons.append(f"issues={len(issues)}")

    # runtime/status.json is optional for health, but if present and broken => warn/fail
    if status.get("ok") is False and "error" in status:
        reasons.append(status["error"])

    # SAFE_HARD_LOCK is an operational WARN (system intentionally blocked)
    if safe_lock:
        reasons.append("SAFE_HARD_LOCK")

    # Treat sanity warnings as WARN
    if warnings:
        reasons.append(f"warnings={len(warnings)}")

    # Heuristic: if sanity failed => FAIL
    if not sanity_ok:
        return ("FAIL", 4, reasons)

    # If SAFE lock or warnings => WARN
    if safe_lock or warnings:
        return ("WARN", 2, reasons)

    return ("OK", 0, reasons)


def main() -> None:
    pretty = ("--pretty" in sys.argv) or ("-p" in sys.argv)

    snap = get_health_snapshot_for_core()
    safe_lock = _is_safe_hard_lock()
    status = _read_runtime_status()

    level, code, reasons = _evaluate(snap, status, safe_lock)

    out: Dict[str, Any] = {
        "ts_utc": _utc_now(),
        "level": level,
        "exit_code": code,
        "reasons": reasons,
        "safe_hard_lock": safe_lock,
        "runtime_status": status,
        "health_snapshot": snap,
    }

    if pretty:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(out, ensure_ascii=False))

    raise SystemExit(code)


if __name__ == "__main__":
    main()
