from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


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

        reasons: List[str] = []

        # STEP1.4.4+: HARD LOCK (file SAFE_MODE) must force SAFE ON
        safe_lock_on = bool(signals.get("safe_lock_on", False))
        if safe_lock_on:
            reasons.append("HARD_LOCK")

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

        # Decide severity
        if not reasons:
            severity = "OK"
        elif "HARD_LOCK" in reasons or "TIME_BACKWARDS" in reasons or "CRIT_LAG" in reasons:
            severity = "CRIT"
        else:
            severity = "WARN"

        should_be_active = bool(reasons)

        # Transition logic
        if should_be_active and not self._state.active:
            self._state.active = True
            self._state.since_ts = now_ts
        elif not should_be_active and self._state.active:
            # NOTE: auto-recovery is planned for a later STEP.
            # For STEP1.4.4 we keep SAFE sticky unless explicitly cleared.
            pass

        # Sticky SAFE: once enabled, remains until manual clear.
        if self._state.active:
            # Keep accumulating reasons (unique, stable order by insertion)
            for r in reasons:
                if r not in self._state.reasons:
                    self._state.reasons.append(r)

            # Update "reason" to the latest most critical / recent one
            self._state.reason = self._select_primary_reason(reasons) or self._state.reason
            self._state.severity = "CRIT" if (
                "HARD_LOCK" in self._state.reasons
                or "TIME_BACKWARDS" in self._state.reasons
                or "CRIT_LAG" in self._state.reasons
            ) else "WARN"
            self._state.policy = self._build_policy(self._state.severity)
        else:
            self._state.severity = severity
            self._state.reason = ""
            self._state.reasons = []
            self._state.policy = self._build_policy("OK")

    def clear(self, reason: str = "MANUAL_CLEAR") -> None:
        """Explicitly clear SAFE MODE state (for future recovery workflows)."""
        now_ts = time.time()
        self._state = SafeModeState(
            active=False,
            severity="OK",
            since_ts=0.0,
            reason=str(reason or "MANUAL_CLEAR"),
            reasons=[],
            policy=self._build_policy("OK"),
        )
        self._last_eval_ts = now_ts

    def public_snapshot(self) -> Dict[str, Any]:
        """Stable, UI-facing SAFE MODE snapshot."""
        st = self._state
        return {
            "active": bool(st.active),
            "severity": str(st.severity),
            "since_ts": float(st.since_ts or 0.0),
            "reason": str(st.reason or ""),
            "reasons": list(st.reasons),
            "policy": dict(st.policy),
            "meta": {
                "crit_lag_s": float(self._crit_lag_s),
                "last_eval_ts": float(self._last_eval_ts or 0.0),
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

    def _build_policy(self, severity: str) -> Dict[str, Any]:
        """Policy is expressed as explicit allow/deny action lists.

        UI must not interpret reasons; it must only apply policy.
        """
        sev = str(severity or "OK").upper()
        if sev == "OK":
            return {
                "deny_actions": [],
                "allow_actions": ["SIM_ALL", "UI_VIEW", "UI_REFRESH"],
                "mode_hint": "NORMAL",
            }

        # SAFE ON: default-deny REAL actions
        deny = [
            "REAL_BUY",
            "REAL_CLOSE",
            "REAL_ANY_ORDER",
        ]
        allow = [
            "SIM_ALL",
            "UI_VIEW",
            "UI_REFRESH",
        ]

        # In WARN we keep the same deny-list (safe defaults everywhere)
        # Future STEPs may relax / add granular allow (e.g. allow REAL_CLOSE only).
        return {
            "deny_actions": deny,
            "allow_actions": allow,
            "mode_hint": "SAFE",
        }
