from __future__ import annotations
import time, threading
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, Any

from runtime.state_manager import StateManager

@dataclass
class Position:
    symbol: str
    qty: float
    entry_price: float
    tp: Optional[float] = None
    sl: Optional[float] = None
    opened_at: float = field(default_factory=lambda: time.time())
    stats: Dict[str, Any] = field(default_factory=dict)

class PositionManager:
    def __init__(self, state: StateManager, logger=None):
        self._state = state
        self._logger = logger or (lambda *a, **k: print(*a))
        self._lock = threading.Lock()

    def log(self, msg: str):
        self._logger(f"{time.strftime('%H:%M:%S')} | {msg}")

    def _data(self):
        return self._state.get("positions", {})

    def get_open_positions(self) -> Dict[str, Position]:
        with self._lock:
            pos = {}
            for k, v in self._data().items():
                pos[k] = Position(**v)
            return pos

    def upsert_position(self, p: Position):
        with self._lock:
            data = self._data()
            data[p.symbol] = asdict(p)
            self._state.set("positions", data)

    def mark_closing(self, symbol: str, flag: bool = True):
        with self._lock:
            data = self._data()
            if symbol in data:
                stats = data[symbol].setdefault("stats", {})
                stats["closing"] = bool(flag)
                self._state.set("positions", data)

    def is_closing(self, symbol: str) -> bool:
        with self._lock:
            data = self._data()
            if symbol in data:
                return bool(data[symbol].get("stats", {}).get("closing"))
            return False

    def close_position(self, symbol: str, reason: str = ""):
        # SAFE-lock to prevent repeated updates during close
        self.mark_closing(symbol, True)
        with self._lock:
            data = self._data()
            data.pop(symbol, None)
            self._state.set("positions", data)
        self.log(f"[POS] {symbol} closed. {('Reason: ' + reason) if reason else ''}")

    def set_tp(self, symbol: str, tp: float):
        with self._lock:
            data = self._data()
            if symbol in data and not data[symbol].get('stats', {}).get('closing'):
                data[symbol]["tp"] = float(tp)
                self._state.set("positions", data)
        self.log(f"[TPSL] {symbol}: TP set -> {tp:.6f}")

    def set_sl(self, symbol: str, sl: float):
        with self._lock:
            data = self._data()
            if symbol in data and not data[symbol].get('stats', {}).get('closing'):
                data[symbol]["sl"] = float(sl)
                self._state.set("positions", data)
        self.log(f"[TPSL] {symbol}: SL set -> {sl:.6f}")

    def update_tp(self, symbol: str, tp: float, tag: str = ""):
        self.set_tp(symbol, tp)
        if tag:
            self.log(f"[TPSL] {symbol}: TP updated by {tag}")

    def update_sl(self, symbol: str, sl: float, tag: str = ""):
        self.set_sl(symbol, sl)
        if tag:
            self.log(f"[TPSL] {symbol}: SL updated by {tag}")

    def update_max_price(self, symbol: str, price: float):
        with self._lock:
            data = self._data()
            if symbol in data:
                stats = data[symbol].setdefault("stats", {})
                if price > float(stats.get("max_price", 0.0)):
                    stats["max_price"] = float(price)
                    self._state.set("positions", data)
                    self.log(f"[POS] {symbol}: max_price -> {price:.6f}")
