from __future__ import annotations

import os
import sys
from typing import Optional

# --- ensure project root in sys.path when run as a script ---
# This allows running: `python runtime/tpsl_loop.py` from project root on Windows.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
# --- end sys.path bootstrap ---

from core.tpsl_autoloop import TpslAutoLoop, TpslConfig, TrailingParams, DynamicParams
from runtime.state_manager import StateManager
from core.position_manager import PositionManager

# optional volatility provider (from price cache ring buffer if available)
def _get_volatility(symbol: str, window: int):
    try:
        from runtime.price_cache import get_window_extrema
        lo, hi = get_window_extrema(symbol, window)
        if lo is None or hi is None or hi == 0:
            return None
        mid = (lo + hi) / 2.0
        if mid <= 0:
            return None
        vol_pct = (hi - lo) / mid * 100.0
        return vol_pct
    except Exception:
        return None

class TpslLoopRunner:
    def __init__(self, settings: dict, get_price_callable):
        tp = settings.get("tpsl_autoloop", {})
        cfg = TpslConfig(
            interval_sec=int(tp.get("interval_sec", 5)),
            enabled=bool(tp.get("enabled", True)),
            mode=str(tp.get("mode", "dynamic")).lower(),
            trailing=TrailingParams(min_move_pct=float(tp.get("min_move_pct", 0.35)),
                                    hard_stop_pct=tp.get("hard_stop_pct")),
            dynamic=DynamicParams(
                enabled=bool(tp.get("dynamic", {}).get("enabled", True)),
                base_pct=float(tp.get("dynamic", {}).get("base_pct", 0.35)),
                min_pct=float(tp.get("dynamic", {}).get("min_pct", 0.20)),
                max_pct=float(tp.get("dynamic", {}).get("max_pct", 1.00)),
                vol_window=int(tp.get("dynamic", {}).get("vol_window", 50)),
            )
        )
        self.state = StateManager()
        self.pm = PositionManager(self.state)
        self.loop = TpslAutoLoop(self.pm, get_price_callable, cfg, _get_volatility)

    def start(self):
        self.loop.start()

    def stop(self):
        self.loop.stop()

_runner: Optional[TpslLoopRunner] = None

def start(settings: dict, get_price_callable):
    global _runner
    _runner = TpslLoopRunner(settings, get_price_callable)
    _runner.start()
    return _runner

def stop():
    global _runner
    if _runner:
        _runner.stop()
