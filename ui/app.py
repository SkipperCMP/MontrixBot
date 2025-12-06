
from __future__ import annotations
import os, sys, tkinter as tk
from tkinter import ttk
from collections import deque
import time

# ensure imports when running as `python ui/app.py`
_THIS = os.path.dirname(__file__)
_ROOT = os.path.abspath(os.path.join(_THIS, os.pardir))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ui.widgets.ticker_panel import LiveTickerPanel
from ui.widgets.deals_journal import DealsJournal
from ui.widgets.coin_details import CoinDetailsPanel

from core.feeds.binance_ws import BinanceMiniTickerThread
from core.feeds.binance_poll import BinancePollThread
try:
    from core.feeds import binance_ws as _mb_ws
    _WS_AVAILABLE = (_mb_ws.websocket is not None)
except Exception:
    _WS_AVAILABLE = False

APP_TITLE = "MontrixBot 0.9.5 — UI"

# --- Ticker / ordering config
FEED_MODE = "auto"   # "auto" | "ws" | "rest" | "demo"
TICKER_SYMBOLS = ["BTCUSDT","ETHUSDT","ADAUSDT","HBARUSDT","BONKUSDT","SOLUSDT","AVAXUSDT","DOGEUSDT","ATOMUSDT"]
PIN_ANCHORS = ["BTCUSDT", "ETHUSDT"]   # всегда слева, если присутствуют
AUTO_SORT = True                       # автосортировка остальных по % (24h)
REORDER_INTERVAL_MS = 1200             # как часто пересортировывать

BINANCE_TRACE = False
BINANCE_INSECURE_SSL = False

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)

        # cache котировок: sym -> {"price":float,"pct":float}
        self._quotes = {s: {"price": 0.0, "pct": 0.0} for s in TICKER_SYMBOLS}
        self._selected = None  # текущий выбранный символ из тикера

        # --- Top ticker panel
        self.ticker = LiveTickerPanel(self, on_symbol_click=self._on_symbol_click, max_visible=12)
        self.ticker.pack(fill=tk.X)
        self.ticker.set_tickers([{"symbol": s, "price": 0.0, "pct": 0.0} for s in TICKER_SYMBOLS])

        # --- Body: split to left(main) / right(details)
        paned = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(paned)

# --- TPSL badge injection (auto-generated) ---
try:
    import json, os
    from ui.tpsl_status_badge import TpslStatusBadge
except Exception:
    TpslStatusBadge = None

def _tpsl_enabled():
    try:
        with open("runtime/settings.json","r",encoding="utf-8") as _f:
            _cfg = json.load(_f)
        return bool(_cfg.get("tpsl_autoloop",{}).get("enabled", True))
    except Exception:
        return False

if TpslStatusBadge:
    try:
        _badge_parent = top if 'top' in globals() else (toolbar if 'toolbar' in globals() else None)
        if _badge_parent is None:
            # as a last resort, place in root if available
            _badge_parent = root if 'root' in globals() else None
        if _badge_parent is not None:
            _tpsl_badge = TpslStatusBadge(_badge_parent, _tpsl_enabled)
            _lbl = _tpsl_badge.mount()
            if _lbl:
                try:
                    _lbl.pack(side="right", padx=8, pady=4)
                except Exception:
                    _lbl.grid(row=0, column=999, padx=8, pady=4, sticky="e")
    except Exception as _e:
        print("TPSL badge injection failed:", _e)
# --- end TPSL badge injection ---
        paned.add(left, weight=4)

        right = ttk.Frame(paned, width=320)
        paned.add(right, weight=0)

        # left content: Notebook + Deals
        nb = ttk.Notebook(left)
        nb.pack(fill=tk.BOTH, expand=True)
        deals_tab = ttk.Frame(nb); nb.add(deals_tab, text="Deals")
        self.deals = DealsJournal(deals_tab); self.deals.frame.pack(fill=tk.BOTH, expand=True)

        # right content: Coin details (initially empty)
        self.coin_details = CoinDetailsPanel(right, width=320, height=260)
        self.coin_details.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # --- feed
        def _on_quote(sym, price, pct):
            sym = (sym or "").upper()
            if not sym:
                return
            # update cache
            q = self._quotes.setdefault(sym, {"price":0.0,"pct":0.0})
            q["price"] = float(price or 0.0)
            q["pct"] = float(pct or 0.0)
            # push to ticker
            try:
                self.after(0, lambda: self.ticker.update_quote(sym, q["price"], q["pct"]))
            except Exception:
                pass
            # update coin details if selected
            if self._selected == sym:
                try:
                    self.after(0, lambda: self.coin_details.on_quote(sym, q["price"], q["pct"]))
                except Exception:
                    pass

        self._feed_thread = None
        started = False
        if FEED_MODE in ("auto","ws") and _WS_AVAILABLE:
            try:
                self._feed_thread = BinanceMiniTickerThread(TICKER_SYMBOLS, _on_quote, trace=BINANCE_TRACE, insecure_ssl=BINANCE_INSECURE_SSL)
                self._feed_thread.start()
                print("[UI] WebSocket feed started")
                started = True
            except Exception as e:
                print("[UI] не удалось запустить WS feed:", e)
                self._feed_thread = None
                started = False
        if (FEED_MODE in ("auto","rest") and not started):
            try:
                self._feed_thread = BinancePollThread(TICKER_SYMBOLS, _on_quote)
                self._feed_thread.start()
                print("[UI] REST polling feed started")
                started = True
            except Exception as e:
                print("[UI] не удалось запустить REST feed:", e)
                self._feed_thread = None
                started = False
        if not started or FEED_MODE == "demo":
            self._start_demo_jitter(_on_quote)

        # periodic reorder for auto-sort/pin
        self.after(REORDER_INTERVAL_MS, self._reorder_push)

    # --- handlers
    def _on_symbol_click(self, sym: str):
        self._selected = sym.upper()
        q = self._quotes.get(self._selected, {"price":0.0,"pct":0.0})
        self.coin_details.set_symbol(self._selected)
        self.coin_details.on_quote(self._selected, q["price"], q["pct"])

    # --- periodic reorder based on cache
    def _reorder_push(self):
        try:
            if AUTO_SORT:
                rows = [{"symbol": s, "price": self._quotes.get(s,{}).get("price",0.0),
                         "pct": self._quotes.get(s,{}).get("pct",0.0)} for s in TICKER_SYMBOLS]
                # split pins and rest
                pins = [r for r in rows if r["symbol"] in PIN_ANCHORS]
                rest = [r for r in rows if r["symbol"] not in PIN_ANCHORS]
                # sort rest by pct desc
                rest.sort(key=lambda r: r["pct"], reverse=True)
                ordered = pins + rest
                # push order to ticker (set_tickers preserves that order)
                self.ticker.set_tickers(ordered)
        except Exception:
            pass
        finally:
            self.after(REORDER_INTERVAL_MS, self._reorder_push)

    def _start_demo_jitter(self, cb):
        import random
        for i,s in enumerate(TICKER_SYMBOLS):
            self._quotes[s] = {"price":100+i*10, "pct":0.0}
        self.ticker.set_tickers([{"symbol": s, "price": self._quotes[s]["price"], "pct": 0.0} for s in TICKER_SYMBOLS])
        def _tick():
            s = random.choice(TICKER_SYMBOLS)
            q = self._quotes[s]
            q["price"] *= (1 + random.uniform(-0.002, 0.002))
            q["pct"] += random.uniform(-0.05, 0.05)
            try: cb(s, q["price"], q["pct"])
            except Exception: pass
            self.after(280, _tick)
        self.after(600, _tick)

    def destroy(self):
        try: self._closing = True
        except Exception: pass
        try:
            if getattr(self, "_feed_thread", None):
                self._feed_thread.stop()
        except Exception:
            pass
        super().destroy()

def main():
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()
