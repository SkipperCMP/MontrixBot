from __future__ import annotations
import time, threading, json, os
from dataclasses import dataclass, field
from typing import Dict, Optional, Literal, Iterable

from core.executor import OrderExecutor
from core.history_retention import apply_retention_for_key

Side = Literal["LONG","SHORT"]

@dataclass
class TPSSLConfig:
    take_profit_pct: float = 0.02
    stop_loss_pct: float = 0.01
    trail_activate_pct: float = 0.015
    trail_step_pct: float = 0.005

@dataclass
class Position:
    symbol: str
    side: Side
    entry_price: float
    qty: float
    opened_ts: float
    tp_price: float
    sl_price: float
    trailing_active: bool = False
    trail_anchor: float = 0.0
    last_ts: float = field(default_factory=time.time)

class TPSLManager:
    def __init__(self, executor: OrderExecutor, config: Optional[TPSSLConfig]=None, journal_path: str="runtime/trades.jsonl"):
        self.ex = executor
        self.cfg = config or TPSSLConfig()
        self._pos: Dict[str, Position] = {}
        self._lock = threading.RLock()
        self.journal_path = journal_path
        os.makedirs(os.path.dirname(journal_path), exist_ok=True)
        try:
            self.recover_from_journal()
        except Exception:
            pass

    def _journal(self, event: dict):
        try:
            event["ts"] = event.get("ts") or time.time()
            with open(self.journal_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

            # STEP1.4.4: log retention (best-effort)
            apply_retention_for_key(self.journal_path, "trades_jsonl")
        except Exception:
            pass

    def _read_journal(self) -> Iterable[dict]:
        if not os.path.exists(self.journal_path):
            return []
        out = []
        try:
            with open(self.journal_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        continue
        except Exception:
            return []
        return out

    def recover_from_journal(self):
        events = list(self._read_journal())
        if not events:
            return
        last_open: Dict[str, dict] = {}
        closed: set[str] = set()
        for ev in events:
            t = ev.get("type")
            sym = (ev.get("symbol") or "").upper()
            if not sym:
                continue
            if t == "OPEN":
                last_open[sym] = ev
            elif t == "CLOSE":
                closed.add(sym)
        for sym, ev in last_open.items():
            if sym in closed:
                continue
            entry = float(ev.get("entry") or 0.0)
            qty = float(ev.get("qty") or 0.0)
            if entry <= 0.0 or qty <= 0.0:
                continue
            tp = entry * (1.0 + self.cfg.take_profit_pct)
            sl = entry * (1.0 - self.cfg.stop_loss_pct)
            self._pos[sym] = Position(
                symbol=sym, side="LONG", entry_price=entry, qty=qty,
                opened_ts=float(ev.get("ts") or time.time()), tp_price=tp, sl_price=sl,
                trailing_active=False, trail_anchor=entry
            )

    def open_long(self, symbol: str, entry_price: float, qty: float):
        with self._lock:
            tp = entry_price * (1.0 + self.cfg.take_profit_pct)
            sl = entry_price * (1.0 - self.cfg.stop_loss_pct)
            self._pos[symbol.upper()] = Position(
                symbol=symbol.upper(), side="LONG", entry_price=entry_price, qty=qty,
                opened_ts=time.time(), tp_price=tp, sl_price=sl, trailing_active=False, trail_anchor=entry_price
            )
            self._journal({"type":"OPEN","symbol":symbol.upper(),"side":"LONG","qty":qty,"entry":entry_price,"tp":tp,"sl":sl})

    def close(self, symbol: str, reason: str):
        with self._lock:
            pos = self._pos.pop(symbol.upper(), None)
        if not pos:
            return
        try:
            side = "SELL" if pos.side == "LONG" else "BUY"
            evt = self.ex.place_order(symbol=pos.symbol, side=side, qty=pos.qty, type_="MARKET")
            self._journal({"type":"CLOSE","symbol":pos.symbol,"reason":reason,"fill_price":evt.price,"qty":evt.qty})
        except Exception as e:
            self._journal({"type":"CLOSE_FAIL","symbol":pos.symbol,"reason":f"{reason}:{e}"})

    def on_price(self, symbol: str, last: float, now: Optional[float]=None):
        now = now or time.time()
        sym = symbol.upper()
        with self._lock:
            pos = self._pos.get(sym)
            if not pos:
                return
            pos.last_ts = now
            if not pos.trailing_active:
                if last >= pos.entry_price * (1.0 + self.cfg.trail_activate_pct):
                    pos.trailing_active = True
                    pos.trail_anchor = last
            if pos.trailing_active:
                if last > pos.trail_anchor:
                    pos.trail_anchor = last
                    pos.sl_price = max(pos.sl_price, pos.trail_anchor * (1.0 - self.cfg.trail_step_pct))
                    pos.tp_price = max(pos.tp_price, pos.trail_anchor * (1.0 + self.cfg.trail_step_pct))
            if last <= pos.sl_price:
                to_close = True
                reason = f"SL_hit({round((last/pos.entry_price-1)*100,2)}%)"
            elif last >= pos.tp_price:
                to_close = True
                reason = f"TP_hit({round((last/pos.entry_price-1)*100,2)}%)"
            else:
                to_close = False
                reason = ""
        if to_close:
            self.close(sym, reason)
