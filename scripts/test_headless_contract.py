"""Headless contract test (offline, UI-free).

What this test proves:
  1) Core SIM primitives can be exercised without importing any UI modules.
  2) A minimal SIM open/close cycle works offline.

Notes:
  - This test intentionally does NOT touch network / exchangeInfo.
  - It may write to runtime/trades.jsonl as part of core behavior.
"""

from __future__ import annotations

import os
import sys
import time


def _ensure_project_root_on_path() -> None:
    root = os.path.dirname(os.path.dirname(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)


def _assert_no_ui_imports() -> None:
    bad = [m for m in sys.modules.keys() if m == "ui" or m.startswith("ui.")]
    if bad:
        raise AssertionError(f"UI modules must NOT be imported in headless test: {bad[:5]}")


def main() -> None:
    _ensure_project_root_on_path()

    # Import core modules only.
    from core.state_engine import StateEngine
    from core.executor import OrderExecutor
    from core.tpsl import TPSLManager, TPSSLConfig

    _assert_no_ui_imports()

    st = StateEngine()
    ex = OrderExecutor(mode="SIM", state=st)
    cfg = TPSSLConfig(take_profit_pct=0.01, stop_loss_pct=0.01, trail_activate_pct=0.005, trail_step_pct=0.002)
    tp = TPSLManager(ex, cfg)
    st.attach_tpsl(tp)

    symbol = "TESTUSDT"
    entry = 1.0
    qty = 10.0

    # Open.
    tp.open_long(symbol, entry_price=entry, qty=qty)

    # Drive a few synthetic ticks.
    for i in range(10):
        price = entry * (1.0 + 0.002 * i)
        st.upsert_ticker(symbol, price, price, price)
        time.sleep(0.01)

    # Close explicitly.
    # TPSLManager exposes close(symbol, reason) (there is no close_long()).
    tp.close(symbol, reason="TEST_EXIT")

    # Sanity: position should be gone.
    if symbol in getattr(tp, "_pos", {}):
        raise AssertionError("Position was not closed")

    _assert_no_ui_imports()
    print("[OK] Headless contract passed (UI-free, offline)")


if __name__ == "__main__":
    main()
