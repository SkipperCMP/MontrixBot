from __future__ import annotations
import time, threading, math
from core import heartbeats as hb
from dataclasses import dataclass, field
from typing import Optional, Callable

from core.position_manager import PositionManager, Position

@dataclass
class TrailingParams:
    min_move_pct: float = 0.35
    hard_stop_pct: Optional[float] = None

@dataclass
class DynamicParams:
    enabled: bool = True
    base_pct: float = 0.35   # базовый шаг трейлинга в %
    min_pct: float = 0.20    # нижняя граница при низкой волатильности
    max_pct: float = 1.00    # верхняя граница при высокой волатильности
    vol_window: int = 50     # окно для оценки волатильности (в ценах)

@dataclass
class TpslConfig:
    interval_sec: int = 5
    enabled: bool = True
    mode: str = "dynamic"  # 'static'|'dynamic'
    trailing: TrailingParams = field(default_factory=TrailingParams)
    dynamic: DynamicParams = field(default_factory=DynamicParams)

class TpslAutoLoop:
    def __init__(self, pm: PositionManager, get_price: Callable[[str], Optional[float]],
                 config: TpslConfig,
                 get_volatility_pct: Optional[Callable[[str, int], Optional[float]]] = None):
        self._pm = pm
        self._get_price = get_price
        self._cfg = config
        self._get_vol = get_volatility_pct
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        if not self._cfg.enabled:
            self._pm.log("TPSL disabled in config; loop won't start.")
            return
        self._pm.log(f"TPSL loop started (interval={self._cfg.interval_sec}s, mode={self._cfg.mode})")
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="TPSL-Autoloop", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        self._pm.log("TPSL loop stopped.")

    def _run(self):
        backoff = 1
        base = self._cfg.interval_sec
        while not self._stop.is_set():
            try:
                hb.beat("tpsl")
                self._tick()
                backoff = 1
                time.sleep(base)
            except Exception as e:
                hb.beat("tpsl")
                self._pm.log(f"[TPSL] Exception: {e}. Backoff {backoff}s")
                time.sleep(min(60, backoff))
                backoff = min(60, backoff * 2)

    def _tick(self):
        positions = self._pm.get_open_positions()
        if not positions:
            return
        for sym, pos in positions.items():
            if self._pm.is_closing(sym):
                continue
            price = self._get_price(sym)
            if price is None:
                continue
            self._process(sym, pos, price)

    # --- helpers ---
    def _clamp(self, v, lo, hi):
        return max(lo, min(hi, v))

    def _calc_trailing_pct(self, symbol: str) -> float:
        if self._cfg.mode == "static" or not self._cfg.dynamic.enabled:
            return max(0.0, float(self._cfg.trailing.min_move_pct))
        # dynamic mode
        base = float(self._cfg.dynamic.base_pct)
        lo = float(self._cfg.dynamic.min_pct)
        hi = float(self._cfg.dynamic.max_pct)
        lookback = int(self._cfg.dynamic.vol_window)
        vol = None
        if self._get_vol:
            try:
                vol = self._get_vol(symbol, lookback)
            except Exception:
                vol = None
        # If no external volatility, approximate using base
        if vol is None:
            return self._clamp(base, lo, hi)
        # Map vol% to multiplier ~ [0.5x .. 2x] around base
        # e.g., 0.5% -> 0.5x, 2% -> ~2x (capped by min/max)
        mult = self._clamp(vol / 1.0, 0.5, 2.0)  # 1.0% vol is neutral
        return self._clamp(base * mult, lo, hi)

    def _process(self, symbol: str, pos: Position, price: float):
        tr = self._cfg.trailing
        # hit checks
        if pos.tp and price > pos.tp:
            self._pm.close_position(symbol, reason=f"TP hit at {price:.6f}")
            return
        if pos.sl and price < pos.sl:
            self._pm.close_position(symbol, reason=f"SL hit at {price:.6f}")
            return

        # track new max
        max_price = pos.stats.get("max_price", pos.entry_price or price)
        if price > max_price:
            self._pm.update_max_price(symbol, price)
            max_price = price

        # determine trailing step
        trailing_pct = self._calc_trailing_pct(symbol)
        if max_price and trailing_pct > 0:
            target_tp = max_price * (1 - trailing_pct / 100.0)
            if (pos.tp or 0) < target_tp:
                self._pm.update_tp(symbol, target_tp, tag=("dynamic" if self._cfg.mode=="dynamic" else "trailing"))

        # optional hard stop
        if tr.hard_stop_pct:
            hard_sl = max_price * (1 - tr.hard_stop_pct / 100.0)
            if (pos.sl or 0) < hard_sl:
                self._pm.update_sl(symbol, hard_sl, tag="hard-stop")
