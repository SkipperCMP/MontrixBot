from __future__ import annotations
import time, threading, json, os, math
from dataclasses import dataclass, field
from typing import Dict, Optional, Literal, Iterable

from core.executor import OrderExecutor
from core.history_retention import apply_retention_for_key

import logging

log = logging.getLogger(__name__)
_LOG_THROTTLE: Dict[str, float] = {}

def _log_throttled(key: str, level: str, msg: str, *, interval_s: float = 60.0, exc_info: bool = False) -> None:
    try:
        now = time.time()
        last = float(_LOG_THROTTLE.get(key, 0.0) or 0.0)
        if (now - last) < interval_s:
            return
        _LOG_THROTTLE[key] = now
        fn = getattr(log, level, log.warning)
        fn(msg, exc_info=exc_info)
    except Exception:
        return

Side = Literal["LONG","SHORT"]

@dataclass
class TPSSLConfig:
    take_profit_pct: float = 0.02
    stop_loss_pct: float = 0.01
    trail_activate_pct: float = 0.015
    trail_step_pct: float = 0.005

    # v1.2.0 — Dynamic SL (wired into TPSLManager autoloop)
    dynamic_sl_enabled: bool = True
    dynamic_vol_window: int = 30              # rolling window of prices
    dynamic_neutral_vol_pct: float = 1.0      # ~1% realized vol => neutral multiplier
    dynamic_step_min_pct: float = 0.002       # clamp for trail step
    dynamic_step_max_pct: float = 0.020       # clamp for trail step
    dynamic_mult_min: float = 0.5             # multiplier clamp
    dynamic_mult_max: float = 2.0

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
        self._price_hist: Dict[str, list[float]] = {}
        self._lock = threading.RLock()
        self.journal_path = journal_path
        os.makedirs(os.path.dirname(journal_path), exist_ok=True)
        try:
            self.recover_from_journal()
        except Exception:
            _log_throttled(
                "tpsl.recover",
                "warning",
                "TPSL: recover_from_journal failed (starting with empty state)",
                interval_s=60.0,
                exc_info=True,
            )

    def _journal(self, event: dict):
        try:
            event["ts"] = event.get("ts") or time.time()
            with open(self.journal_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

            # STEP1.4.4: log retention (best-effort)
            apply_retention_for_key(self.journal_path, "trades_jsonl")
        except Exception:
            _log_throttled(
                "tpsl.journal.write",
                "warning",
                f"TPSL: journal write failed ({self.journal_path})",
                interval_s=60.0,
                exc_info=True,
            )

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
                        _log_throttled(
                            "tpsl.journal.bad_line",
                            "debug",
                            "TPSL: bad journal line skipped",
                            interval_s=120.0,
                            exc_info=True,
                        )
                        continue
        except Exception:
            _log_throttled(
                "tpsl.journal.read",
                "warning",
                f"TPSL: journal read failed ({self.journal_path})",
                interval_s=60.0,
                exc_info=True,
            )
            return []
        return out

    # ----------------- v1.2.0 Dynamic SL helpers -----------------

    def _record_price(self, sym: str, last: float) -> None:
        try:
            s = str(sym or "").upper()
            if not s:
                return
            v = float(last)
        except Exception:
            return

        w = int(getattr(self.cfg, "dynamic_vol_window", 30) or 30)
        w = max(5, min(500, w))
        arr = self._price_hist.get(s)
        if arr is None:
            arr = []
            self._price_hist[s] = arr
        arr.append(v)
        if len(arr) > w:
            del arr[: len(arr) - w]

    def _realized_vol_pct(self, sym: str) -> float:
        arr = self._price_hist.get(str(sym or "").upper()) or []
        if len(arr) < 6:
            return 0.0

        # realized vol approximation: stddev of pct returns (in %)
        rets: list[float] = []
        prev = float(arr[0])
        for x in arr[1:]:
            cur = float(x)
            if prev > 0:
                rets.append(((cur / prev) - 1.0) * 100.0)
            prev = cur

        if len(rets) < 5:
            return 0.0

        m = sum(rets) / float(len(rets))
        var = 0.0
        for r in rets:
            d = (r - m)
            var += d * d
        var = var / float(max(1, (len(rets) - 1)))
        return float(math.sqrt(var))

    def _dynamic_trail_step_pct(self, sym: str) -> float:
        base = float(getattr(self.cfg, "trail_step_pct", 0.005) or 0.005)

        enabled = bool(getattr(self.cfg, "dynamic_sl_enabled", False))
        if not enabled:
            return max(0.0, base)

        vol = self._realized_vol_pct(sym)
        neutral = float(getattr(self.cfg, "dynamic_neutral_vol_pct", 1.0) or 1.0)
        neutral = max(0.1, neutral)

        mult = vol / neutral
        mult_min = float(getattr(self.cfg, "dynamic_mult_min", 0.5) or 0.5)
        mult_max = float(getattr(self.cfg, "dynamic_mult_max", 2.0) or 2.0)
        mult = max(mult_min, min(mult_max, mult))

        step = base * mult
        lo = float(getattr(self.cfg, "dynamic_step_min_pct", 0.002) or 0.002)
        hi = float(getattr(self.cfg, "dynamic_step_max_pct", 0.020) or 0.020)
        step = max(lo, min(hi, step))
        return max(0.0, float(step))

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

            # v1.2.0: Dynamic SL is driven by the same on_price autoloop (rolling vol)
            self._record_price(sym, last)

            pos.last_ts = now
            if not pos.trailing_active:
                if last >= pos.entry_price * (1.0 + self.cfg.trail_activate_pct):
                    pos.trailing_active = True
                    pos.trail_anchor = last
            if pos.trailing_active:
                if last > pos.trail_anchor:
                    pos.trail_anchor = last

                    step_pct = self._dynamic_trail_step_pct(sym)

                    pos.sl_price = max(pos.sl_price, pos.trail_anchor * (1.0 - step_pct))
                    pos.tp_price = max(pos.tp_price, pos.trail_anchor * (1.0 + step_pct))
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
