from __future__ import annotations

from dataclasses import dataclass
from typing import List

from core.autonomy_policy import AutonomyPolicyStore
from core.trading_state_machine import TradingStateMachine
from core.types_runtime import TradingState


@dataclass(frozen=True)
class PermissionResult:
    allow: bool
    reasons: List[str]


def can_open_new_position_basic(policy: AutonomyPolicyStore, fsm: TradingStateMachine) -> PermissionResult:
    """
    Safety Wiring rule-set (no Gate):

    Важно: мы НЕ выбираем одну “главную” причину.
    Мы аккумулируем все факты-блокировки и отдаём reasons как List[str].

    Canonical codes:
      - "MANUAL_STOP"
      - "AUTO_PAUSED"
      - "TECH_STOP_ACTIVE"
      - "TECH_STOP:<DETAIL>" (e.g. "TECH_STOP:API_KEYS_MISSING")
    """

    reasons: List[str] = []

    def _add(code: str) -> None:
        c = str(code).strip()
        if c and c not in reasons:
            reasons.append(c)

    # 1) Policy manual stop is a fact (absolute)
    if policy.is_hard_stop_active():
        _add("MANUAL_STOP")

    # 1b) SAFE HARD_LOCK (file-based) is a fact-based stop (v1.2.0 safety)
    try:
        from tools.safe_lock import is_safe_on  # file SAFE_MODE in project root
        if bool(is_safe_on()):
            _add("SAFE_HARD_LOCK")
    except Exception:
        # SAFE lock must never break permission surface
        pass

    # 2) FSM state + pause reasons (fact-based)
    try:
        state = fsm.get_state().value
    except Exception:
        state = None

    try:
        rs = fsm.get_pause_reasons()
    except Exception:
        rs = []

    rs_str = [str(r).strip() for r in (rs or []) if str(r).strip()]
    rs_low = [s.lower() for s in rs_str]

    is_tech_stop = ("tech stop" in rs_low)
    is_manual_stop = ("manual stop" in rs_low)

    # Manual stop can also be expressed via FSM reasons
    if (state == TradingState.HARD_STOPPED.value) and is_manual_stop:
        _add("MANUAL_STOP")

    # TECH STOP (fact): include both active + detail (if any)
    if is_tech_stop:
        _add("TECH_STOP_ACTIVE")

        detail_u = ""
        for s in rs_str:
            if s.lower() == "tech stop":
                continue
            detail_u = s.upper()
            break

        if detail_u:
            # accept legacy / mixed formats
            if detail_u.startswith("TECH_STOP:"):
                detail_u = detail_u.split(":", 1)[1]
            if detail_u.startswith("TECH:"):
                detail_u = detail_u.replace("TECH:", "", 1)

            _add(f"TECH_STOP:{detail_u}")

    # AUTO_PAUSED (fact)
    if state == TradingState.AUTO_PAUSED.value:
        _add("AUTO_PAUSED")

    if reasons:
        return PermissionResult(False, reasons)

    return PermissionResult(True, [])

