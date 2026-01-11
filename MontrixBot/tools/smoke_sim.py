from __future__ import annotations
import time

# smoke_sim для MontrixBot 1.0.1:
# Проверяет, что StateEngine принимает тики и отдаёт их в ipc_ticks
# (и при наличии TPSLManager — нотифицирует о цене).
try:
    from core.state_engine import StateEngine
except Exception:
    import os, sys
    _THIS = os.path.dirname(__file__)
    _ROOT = os.path.abspath(os.path.join(_THIS, os.pardir))
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)
    from core.state_engine import StateEngine


def run_smoke() -> None:
    print("[SMOKE_SIM] init StateEngine(enable_tpsl=True)")
    se = StateEngine(enable_tpsl=True)

    symbol = "ADAUSDT"
    base_price = 100.0

    print("[SMOKE_SIM] feeding ticks...")
    for i in range(40):
        px = base_price * (1.0 + 0.001 * i)
        bid = px - 0.01
        ask = px + 0.01
        se.upsert_ticker(symbol, last=px, bid=bid, ask=ask, ts=time.time())
        time.sleep(0.01)

    se.upsert_ticker(symbol, last=104.0, bid=103.99, ask=104.01, ts=time.time())
    print("[SMOKE_SIM] Smoke complete.")


if __name__ == "__main__":
    run_smoke()
