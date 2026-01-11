from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import os

import logging
import time

log = logging.getLogger(__name__)
_LOG_THROTTLE: Dict[str, float] = {}

def _log_throttled(key: str, msg: str, *, interval_s: float = 120.0):
    try:
        now = time.time()
        last = _LOG_THROTTLE.get(key, 0.0)
        if now - last < interval_s:
            return
        _LOG_THROTTLE[key] = now
        log.exception(msg)
    except Exception:
        return

from . import runtime_sanity
from . import heartbeats as hb
from .history_retention import apply_retention_for_key

ParsedLine = Tuple[str, str, str, str, str, str, Dict[str, str]]


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

def get_health_snapshot_for_core() -> Dict[str, Any]:
    """
    Core-facing aggregated health snapshot.

    Used ONLY by StateEngine.snapshot().
    UI must not call this directly.
    """
    snap: Dict[str, Any] = {}

    # runtime sanity
    try:
        snap["sanity"] = get_runtime_sanity_report()
    except Exception:
        _log_throttled(
            "health_api.sanity",
            "health_api: failed to get runtime sanity report",
            interval_s=120.0,
        )
        snap["sanity"] = {
            "ok": False,
            "issues": ["sanity_unavailable"],
            "warnings": [],
            "summary": {},
        }

    # component heartbeats (WS / TPSL / Executor)
    try:
        snap["heartbeats"] = hb.snapshot()
    except Exception:
        _log_throttled(
            "health_api.heartbeats",
            "health_api: failed to collect component heartbeats",
            interval_s=120.0,
        )
        snap["heartbeats"] = {"ts": {}, "age_s": {}, "now": time.time()}

    # health (snapshot-only; file-based health.log is forbidden)
    snap["log"] = {}

    return snap
