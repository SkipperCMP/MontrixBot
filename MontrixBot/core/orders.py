# core/orders.py — DRY-run debug print for transparency
import time


def _debug_dryrun(side, symbol, price, qty):
    print(f"[DRY] {symbol} {side} price={price} qty={qty} ts={int(time.time()*1000)}")


def place_order(side, symbol, price, qty, mode="SIM"):
    """
    Simplified order placer.
    - In non-REAL modes prints a DEBUG line and returns a fake response.
    - REAL mode path must be implemented in your codebase.

    STEP 2.0 — Safety Wiring #2 (HARDENING at execution point):
      - For BUY (entry) we enforce trading permission check here (unbypassable).
      - For SELL/close we do not block.
      - No GateEngine, no Auto-REAL.
    """
    _side = str(side or "BUY").upper()

    # --- HARD execution-level permission gate (entry only) ---
    if _side == "BUY":
        try:
            from core.autonomy_policy import AutonomyPolicyStore
            from core.trading_state_machine import TradingStateMachine
            from core.trade_permission import can_open_new_position_basic

            perm = can_open_new_position_basic(AutonomyPolicyStore(), TradingStateMachine())
            if not bool(getattr(perm, "allow", False)):
                reasons = list(getattr(perm, "reasons", []) or [])
                return {
                    "status": "REJECTED",
                    "reason": "TRADING_PERMISSION_DENIED",
                    "why_not": reasons,
                    "mode": mode,
                }
        except Exception:
            # Fail-safe: if permission check fails, block entry at execution point
            return {
                "status": "REJECTED",
                "reason": "TRADING_PERMISSION_CHECK_FAILED",
                "why_not": ["POLICY_LOCK"],
                "mode": mode,
            }

    # --- existing behavior ---
    if mode != "REAL":
        _debug_dryrun(_side, symbol, price, qty)
        return {"status": "FILLED", "orderId": int(time.time() * 1000), "mode": mode}
    else:
        raise NotImplementedError("REAL mode place_order must be implemented")
