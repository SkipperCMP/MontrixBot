
# core/orders.py — DRY-run debug print for transparency
import time

def _debug_dryrun(side, symbol, price, qty):
    print(f"[DRY] {symbol} {side} price={price} qty={qty} ts={int(time.time()*1000)}")

def place_order(side, symbol, price, qty, mode="SIM"):
    """
    Simplified order placer.
    - In non-REAL modes prints a DEBUG line and returns a fake response.
    - REAL mode path must be implemented in your codebase.
    """
    if mode != "REAL":
        _debug_dryrun(side, symbol, price, qty)
        return {"status": "FILLED", "orderId": int(time.time()*1000), "mode": mode}
    else:
        raise NotImplementedError("REAL mode place_order must be implemented")
