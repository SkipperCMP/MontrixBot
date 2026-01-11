from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

log = logging.getLogger(__name__)


# NOTE:
# SafeMode is a CORE-owned behavior/policy layer.
# UI must only *consume* the exported snapshot and block UI actions accordingly.


DEFAULT_CRIT_LAG_S: float = 5.0


@dataclass
class SafeModeState:
    active: bool = False
    severity: str = "OK"  # OK | WARN | CRIT
    since_ts: float = 0.0
    reason: str = ""
    reasons: List[str] = field(default_factory=list)

    # policy is intentionally minimal + stable for UI consumption
    policy: Dict[str, Any] = field(default_factory=dict)


class SafeModeManager:
    """Derives SAFE MODE state + policy from core health signals.

    This manager MUST NOT depend on UI. It is evaluated by StateEngine and
    exported via snapshot() for UI consumption.
    """

    def __init__(self, crit_lag_s: float = DEFAULT_CRIT_LAG_S) -> None:
        # CORE SAFE (sticky CRIT_LAG) в PRODUCT/Manual UX выключен по умолчанию.
        # Включить можно явным env-флагом:
        #   MB_SAFE_CORE_ENABLED=1
        self._enabled: bool = str(os.getenv("MB_SAFE_CORE_ENABLED", "0")).strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

        self._crit_lag_s: float = float(crit_lag_s)
        self._state: SafeModeState = SafeModeState()
        self._last_eval_ts: float = 0.0

    def evaluate(self, signals: Dict[str, Any]) -> None:
        """Update internal SAFE MODE state using the passed signals.

        Expected keys (best-effort):
        - core_lag_s: float
        - core_stall: bool
        - core_time_backwards: bool
        - core_time_backwards_delta_s: float
        - core_time_backwards_count: int
        """
        now_ts = time.time()
        self._last_eval_ts = now_ts

        # PRODUCT/MANUAL UX: CORE SAFE может быть отключён.
        # В этом режиме SAFE не влияет на торговлю и не блокирует UI/REAL.
        if not getattr(self, "_enabled", True):
            self._state.active = False
            self._state.severity = "OK"
            self._state.since_ts = 0.0
            self._state.reason = "DISABLED"
            self._state.reasons = []
            self._state.policy = self._build_policy("OK", [])
            return

        reasons: List[str] = []

        # STEP1.4.4+: HARD LOCK (file SAFE_MODE) — единственный источник полного стопа REAL.
        safe_lock_on = bool(signals.get("safe_lock_on", False))
        if safe_lock_on:
            reasons.append("HARD_LOCK")

        # Остальные сигналы считаем диагностикой/инфо (НЕ блокируют торговлю напрямую).
        core_time_backwards = bool(signals.get("core_time_backwards", False))
        if core_time_backwards:
            reasons.append("TIME_BACKWARDS")

        core_stall = bool(signals.get("core_stall", False))
        if core_stall:
            reasons.append("CORE_STALL")

        try:
            core_lag_s = float(signals.get("core_lag_s", 0.0) or 0.0)
        except Exception:
            core_lag_s = 0.0

        if core_lag_s >= self._crit_lag_s:
            reasons.append("CRIT_LAG")

        # Severity (для отображения в UI/логах), но не для блокировки.
        if not reasons:
            severity = "OK"
        elif "HARD_LOCK" in reasons:
            severity = "CRIT"
        elif "TIME_BACKWARDS" in reasons or "CRIT_LAG" in reasons:
            severity = "CRIT"
        else:
            severity = "WARN"

        # Активным SAFE считаем ТОЛЬКО HARD_LOCK (File SAFE).
        should_be_active = ("HARD_LOCK" in reasons)

        # Transition notifications — только для HARD_LOCK enter/exit
        if should_be_active and not self._state.active:
            self._state.active = True
            self._state.since_ts = now_ts
            try:
                from core.notifications_center import get_notification_center
                get_notification_center().emit_now(
                    level="ERROR",
                    topic="safe",
                    message="SAFE HARD_LOCK entered",
                    meta={"severity": "CRIT", "reasons": list(reasons)},
                )
            except Exception:
                pass
        elif (not should_be_active) and self._state.active:
            # HARD_LOCK снят -> выходим из SAFE
            self._state.active = False
            self._state.since_ts = 0.0
            try:
                from core.notifications_center import get_notification_center
                get_notification_center().emit_now(
                    level="INFO",
                    topic="safe",
                    message="SAFE HARD_LOCK cleared",
                    meta={"reason": "HARD_LOCK_OFF"},
                )
            except Exception:
                pass

        # Обновляем snapshot-данные (информативно), но policy блокирует только при HARD_LOCK.
        self._state.severity = "CRIT" if should_be_active else severity
        self._state.reasons = list(reasons)
        self._state.reason = self._select_primary_reason(reasons) or ""
        self._state.policy = self._build_policy(self._state.severity, reasons)

    def clear(self, reason: str = "MANUAL_CLEAR") -> None:
        """Explicitly clear SAFE MODE state (for future recovery workflows)."""
        now_ts = time.time()
        self._state = SafeModeState(
            active=False,
            severity="OK",
            since_ts=0.0,
            reason=str(reason or "MANUAL_CLEAR"),
            reasons=[],
            policy=self._build_policy("OK", []),
        )
        self._last_eval_ts = now_ts
        try:
            from core.notifications_center import get_notification_center
            get_notification_center().emit_now(
                level="INFO",
                topic="safe",
                message="SAFE MODE cleared",
                meta={"reason": str(reason or "MANUAL_CLEAR")},
            )
        except Exception:
            pass

    def public_snapshot(self) -> Dict[str, Any]:
        """Stable, UI-facing SAFE MODE snapshot."""
        st = self._state
        return {
            "enabled": bool(getattr(self, "_enabled", True)),
            "active": bool(st.active),
            "severity": str(st.severity),
            "since_ts": float(st.since_ts or 0.0),
            "reason": str(st.reason or ""),
            "reasons": list(st.reasons),
            "policy": dict(st.policy),
            "meta": {
                "crit_lag_s": float(self._crit_lag_s),
                "last_eval_ts": float(self._last_eval_ts or 0.0),
                "safe_lock_on": bool("HARD_LOCK" in st.reasons),
            },
        }

    # ----------------- internals -----------------

    def _select_primary_reason(self, reasons_now: List[str]) -> Optional[str]:
        if not reasons_now:
            return None
        # priority order: HARD_LOCK > TIME_BACKWARDS > CRIT_LAG > CORE_STALL
        for r in ("HARD_LOCK", "TIME_BACKWARDS", "CRIT_LAG", "CORE_STALL"):
            if r in reasons_now:
                return r
        return reasons_now[-1]

    def _build_policy(self, severity: str, reasons: List[str]) -> Dict[str, Any]:
        """Policy is expressed as explicit allow/deny action lists.

        IMPORTANT (PRODUCT-MODE):
          - CORE SAFE must NOT block REAL by heuristics (lag/stall/backwards).
          - Only HARD_LOCK (file SAFE_MODE) may deny REAL actions.
        """
        sev = str(severity or "OK").upper()
        rs = list(reasons or [])

        # Default: do not deny REAL actions here (no hidden blocks)
        base = {
            "deny_actions": [],
            "allow_actions": ["SIM_ALL", "UI_VIEW", "UI_REFRESH"],
            "mode_hint": "NORMAL",
            "info_only": True if sev != "OK" else False,
        }

        # Only File SAFE hard lock is allowed to deny REAL
        if "HARD_LOCK" in rs:
            return {
                "deny_actions": ["REAL_BUY", "REAL_CLOSE", "REAL_ANY_ORDER"],
                "allow_actions": ["SIM_ALL", "UI_VIEW", "UI_REFRESH"],
                "mode_hint": "LOCKED",
                "info_only": False,
            }

        return base

def request_panic(reason: str = "PANIC") -> None:
    """
    Core-owned external PANIC trigger.

    This is the ONLY supported entrypoint for runtime/tools to request PANIC.
    The minimal, safe action here is to enable the SAFE hard-lock (file SAFE_MODE),
    which is then detected by StateEngine and forces SAFE policy.

    NOTE:
    - No UI authority.
    - Best-effort: must not raise.
    """
    r = str(reason or "PANIC")
    try:
        from core.notifications_center import get_notification_center
        get_notification_center().emit_now(
            level="ERROR",
            topic="panic",
            message="PANIC requested",
            meta={"reason": r},
        )
    except Exception:
        pass
    try:
        from tools.safe_lock import enable_safe
        enable_safe()
        log.warning("PANIC requested: SAFE hard-lock enabled (reason=%s)", r)
    except Exception:
        # PANIC must never be silent
        log.exception(
            "PANIC requested but failed to enable SAFE hard-lock (reason=%s)", r
        )

