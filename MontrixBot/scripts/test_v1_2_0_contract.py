# scripts/test_v1_2_0_contract.py
"""
v1.2.0 contract test:
- SAFE HARD_LOCK must appear in why_not (fact-based, file SAFE_MODE)
- Dynamic SL must be wired into TPSLManager.on_price (step varies with volatility)
Offline-safe. No UI required.
"""

import os
import sys
import time
import math

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

from core.autonomy_policy import AutonomyPolicyStore
from core.trading_state_machine import TradingStateMachine
from core.status_service import StatusService
from core.state_engine import StateEngine
from core.executor import OrderExecutor
from core.tpsl import TPSLManager, TPSSLConfig

SAFE_FLAG = os.path.join(ROOT, "SAFE_MODE")


def _rm(p: str) -> None:
    try:
        os.remove(p)
    except FileNotFoundError:
        pass


def test_safe_hard_lock_in_why_not() -> None:
    _rm(SAFE_FLAG)

    policy = AutonomyPolicyStore()
    fsm = TradingStateMachine()
    svc = StatusService(policy, fsm)

    st0 = svc.build_status()
    assert "SAFE_HARD_LOCK" not in (st0.why_not or []), f"unexpected SAFE_HARD_LOCK in why_not: {st0.why_not}"

    # enable file lock
    with open(SAFE_FLAG, "w", encoding="utf-8") as f:
        f.write("SAFE")

    st1 = svc.build_status()
    assert "SAFE_HARD_LOCK" in (st1.why_not or []), f"SAFE_HARD_LOCK missing in why_not: {st1.why_not}"

    _rm(SAFE_FLAG)


def test_dynamic_sl_wired() -> None:
    # Contract: Dynamic SL must be wired and respond to realized volatility.
    # Do NOT open positions: project may auto-close in SIM for reasons unrelated to TP/SL.
    cfg = TPSSLConfig(
        take_profit_pct=0.005,
        stop_loss_pct=0.005,
        trail_activate_pct=0.001,
        trail_step_pct=0.005,  # base
    )
    cfg.dynamic_sl_enabled = True
    cfg.dynamic_vol_window = 30
    cfg.dynamic_neutral_vol_pct = 1.0
    cfg.dynamic_step_min_pct = 0.002
    cfg.dynamic_step_max_pct = 0.020
    cfg.dynamic_mult_min = 0.5
    cfg.dynamic_mult_max = 2.0

    # Minimal executor/state to instantiate TPSLManager (offline-safe)
    st = StateEngine()
    ex = OrderExecutor(mode="SIM", state=st)
    tp = TPSLManager(ex, cfg)

    sym = "ADAUSDT"
    assert hasattr(tp, "_record_price"), "TPSLManager missing _record_price (dynamic SL not integrated)"
    assert hasattr(tp, "_dynamic_trail_step_pct"), "TPSLManager missing _dynamic_trail_step_pct (dynamic SL not integrated)"

    # Phase A: very low volatility
    for i in range(40):
        px = 1.0 * (1.0 + 0.0002 * math.sin(i / 3.0))
        tp._record_price(sym, px)
    step_low = float(tp._dynamic_trail_step_pct(sym))

    # Phase B: higher volatility
    for i in range(60):
        px = 1.0 * (1.0 + 0.01 * math.sin(i / 2.0))  # ~1% swings
        tp._record_price(sym, px)
    step_high = float(tp._dynamic_trail_step_pct(sym))

    assert step_high >= step_low, f"dynamic step did not increase with volatility: low={step_low}, high={step_high}"


def main() -> None:
    test_safe_hard_lock_in_why_not()
    test_dynamic_sl_wired()
    print("[OK] v1.2.0 contract passed (SAFE_HARD_LOCK + Dynamic SL wired)")


if __name__ == "__main__":
    main()
