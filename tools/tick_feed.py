
from __future__ import annotations
import time, math, random

# Robust imports whether run as "python tools/tick_feed.py" or "python -m tools.tick_feed"
try:
    from tools.ipc_ticks import append_tick
except Exception:
    import os, sys
    _THIS = os.path.dirname(__file__)
    _ROOT = os.path.abspath(os.path.join(_THIS, os.pardir))
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)
    from tools.ipc_ticks import append_tick

def main(symbol: str = "ADAUSDT", base: float = 1.04, secs: int = 30, dt: float = 0.25):
    """
    Лёгкая подача тиков напрямую в ticks_stream.jsonl,
    чтобы панель бегала даже без запуска движка/симулятора.
    """
    t0 = time.time()
    i = 0
    while time.time() - t0 < secs:
        i += 1
        wiggle = 0.002 * math.sin(i/5.0) + random.uniform(-0.001, 0.001)
        price = max(0.000001, base * (1.0 + wiggle))
        append_tick({"symbol": symbol, "price": price, "ts": time.time()})
        time.sleep(dt)

if __name__ == "__main__":
    main()
