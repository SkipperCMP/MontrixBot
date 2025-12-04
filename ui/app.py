
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
from ui.widgets.positions_panel import build_activepos_ui  # ActivePanel UX3

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

        # --- Body: main vertical split (top: текущий layout, bottom: PRO-каркас)
        vpaned = ttk.Panedwindow(self, orient=tk.VERTICAL)
        vpaned.pack(fill=tk.BOTH, expand=True)

        # top area: сохраняем существующий layout (Deals + CoinDetails)
        top_area = ttk.Frame(vpaned)
        vpaned.add(top_area, weight=3)

        # bottom area: будущий PRO-UI (каркас 1.2.4)
        bottom_area = ttk.Frame(vpaned)
        vpaned.add(bottom_area, weight=2)

        self._pro_bottom_area = bottom_area  # пригодится в следующих шагах

        # --- Body: split to left(main) / right(details)
        paned = ttk.Panedwindow(top_area, orient=tk.HORIZONTAL)
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

        # --- PRO-UI placeholders (STEP1.2.4)
        # Сетка: сверху основная область (chart+active), справа позиции/ордера, снизу логи+кнопки+статус
        self._pro_bottom_area.rowconfigure(0, weight=3)
        self._pro_bottom_area.rowconfigure(1, weight=0)
        self._pro_bottom_area.columnconfigure(0, weight=3)
        self._pro_bottom_area.columnconfigure(1, weight=2)

        left_block = ttk.Frame(self._pro_bottom_area)
        left_block.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        right_block = ttk.Frame(self._pro_bottom_area)
        right_block.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)

        bottom_bar = ttk.Frame(self._pro_bottom_area)
        bottom_bar.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=4, pady=(0, 4))

        # Левый блок: график + панель активной позиции
        self.frame_chart = ttk.Frame(left_block)
        self.frame_chart.pack(fill=tk.BOTH, expand=True)
        ttk.Label(self.frame_chart, text="Chart panel (placeholder)").pack()

        self.frame_active = ttk.Frame(left_block)
        self.frame_active.pack(fill=tk.X, expand=False, pady=(4, 0))

        # Строим реальную панель Active positions (UX3) внутри frame_active
        build_activepos_ui(self)

        # Правый блок: таблицы позиций и ордеров
        self.frame_positions = ttk.Frame(right_block)
        self.frame_positions.pack(fill=tk.BOTH, expand=True)
        ttk.Label(self.frame_positions, text="Positions table (placeholder)").pack(anchor="w")

        self.frame_orders = ttk.Frame(right_block)
        self.frame_orders.pack(fill=tk.X, expand=False, pady=(4, 0))
        ttk.Label(self.frame_orders, text="Orders table (placeholder)").pack(anchor="w")

        # Нижняя полоса: лог + контролы + статус
        self.frame_log = ttk.Frame(bottom_bar)
        self.frame_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Label(self.frame_log, text="Log panel (placeholder)").pack(anchor="w")

        side_controls = ttk.Frame(bottom_bar)
        side_controls.pack(side=tk.RIGHT, fill=tk.Y)

        self.frame_controls = ttk.Frame(side_controls)
        self.frame_controls.pack(fill=tk.X)
        ttk.Label(self.frame_controls, text="Controls bar (placeholder)").pack(anchor="e")

        self.frame_status = ttk.Frame(side_controls)
        self.frame_status.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(self.frame_status, text="Status bar (placeholder)").pack(anchor="e")

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

    def _set_active_text(self, text: str) -> None:
        """
        Заполняет панель Active positions и подсвечивает:
        - pnl_pos / pnl_neg: PnL% (зелёный/красный)
        - side_long / side_short: колонка Side (LONG / SHORT)

        Формат строк задаётся update_active_rows:
            header -> "Symbol Side Qty Entry Last Value Pnl% TP SL Hold Act Conf"
            далее строки с теми же колонками.
        """
        box = getattr(self, "active_box", None)
        if box is None:
            return

        # кэшируем последний текст, чтобы не перерисовывать панель без изменений
        new_text = text or ""
        try:
            last_text = getattr(self, "_last_active_text", "")
        except Exception:
            last_text = ""
        if new_text == last_text:
            return
        try:
            self._last_active_text = new_text
        except Exception:
            # если не удалось сохранить кэш — продолжаем без оптимизации
            pass

        lines = new_text.splitlines()

        try:
            box.configure(state="normal")
            box.delete("1.0", "end")
            if not lines:
                box.insert("1.0", "— no active positions —")
                box.configure(state="disabled")
                return

            # вставляем текст построчно
            for idx, line in enumerate(lines, start=1):
                if idx > 1:
                    box.insert("end", "\n")
                box.insert("end", line)

            # Если нет заголовка с 'Pnl%' — нечего раскрашивать
            if not any("Pnl%" in ln for ln in lines):
                box.configure(state="disabled")
                return

            # Начиная с 3-й строки (после header и разделителя) раскрашиваем Side и PnL
            for row_idx, line in enumerate(lines, start=1):
                if row_idx <= 2:
                    continue  # header + "----"

                try:
                    parts = line.split()
                    # 0:Symbol 1:Side 2:Qty 3:Entry 4:Last 5:Value 6:Pnl% ...
                except Exception:
                    continue

                # --- подсветка Side ---
                try:
                    side_token = parts[1]
                    side_u = side_token.upper()
                    side_tag = None
                    if side_u.startswith("LONG") or side_u.startswith("BUY"):
                        side_tag = "side_long"
                    elif side_u.startswith("SHORT") or side_u.startswith("SELL"):
                        side_tag = "side_short"

                    if side_tag:
                        col_start = line.find(side_token)
                        if col_start >= 0:
                            col_end = col_start + len(side_token)
                            try:
                                box.tag_add(
                                    side_tag,
                                    f"{row_idx}.{col_start}",
                                    f"{row_idx}.{col_end}",
                                )
                            except Exception:
                                pass
                except Exception:
                    pass

                # --- подсветка PnL% ---
                try:
                    pnl_token = parts[6]
                except Exception:
                    continue

                # чистим от процентов и плюсиков
                raw = pnl_token.replace("%", "").replace("+", "").strip()
                try:
                    pnl_val = float(raw)
                except Exception:
                    continue

                if pnl_val > 0.0:
                    tag = "pnl_pos"
                elif pnl_val < 0.0:
                    tag = "pnl_neg"
                else:
                    continue

                col_start = line.find(pnl_token)
                if col_start < 0:
                    continue
                col_end = col_start + len(pnl_token)

                try:
                    box.tag_add(
                        tag,
                        f"{row_idx}.{col_start}",
                        f"{row_idx}.{col_end}",
                    )
                except Exception:
                    pass

            box.configure(state="disabled")
        except tk.TclError:
            # окно/виджет уже уничтожено — игнорируем обновление панели
            return

    def _on_reset_sim(self) -> None:
        """Reset SIM для PRO-UI (заглушка: просто очищает панель)."""
        try:
            self._set_active_text("— no active positions —")
        except Exception:
            pass

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
