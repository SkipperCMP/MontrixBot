
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from collections import deque
import threading, time, json, urllib.request

THEME = {
    "bg": "#151719",
    "tile": "#1d2023",
    "text": "#d7dde4",
    "muted": "#9aa3ad",
    "up": "#7ddc84",
    "down": "#ff7a7a",
}

class CoinDetailsPanel(ttk.Frame):
    """
    Простая карточка монеты: символ, цена, 24h %/high/low/vol и мини-спарклайн.
    API:
        set_symbol(sym)
        on_quote(sym, price, pct)  # для обновления цены
    """
    def __init__(self, master, width=320, height=260):
        super().__init__(master)
        style = ttk.Style(self)
        style.configure("Coin.Tile.TFrame", background=THEME["tile"])
        style.configure("Coin.Title.TLabel", background=THEME["tile"], foreground=THEME["text"], font=("", 12, "bold"))
        style.configure("Coin.Text.TLabel", background=THEME["tile"], foreground=THEME["text"])
        style.configure("Coin.Muted.TLabel", background=THEME["tile"], foreground=THEME["muted"])

        wrap = ttk.Frame(self, style="Coin.Tile.TFrame")
        wrap.pack(fill=tk.BOTH, expand=True)

        # header
        top = ttk.Frame(wrap, style="Coin.Tile.TFrame")
        top.pack(fill=tk.X, padx=8, pady=(8,4))
        self._sym = ttk.Label(top, text="—", style="Coin.Title.TLabel")
        self._price = ttk.Label(top, text="0", style="Coin.Title.TLabel")
        self._sym.pack(side=tk.LEFT); self._price.pack(side=tk.RIGHT)

        # stats
        grid = ttk.Frame(wrap, style="Coin.Tile.TFrame"); grid.pack(fill=tk.X, padx=8, pady=(4,4))
        self._pct = ttk.Label(grid, text="(+0.00%)", style="Coin.Text.TLabel")
        self._hl  = ttk.Label(grid, text="H/L: — / —", style="Coin.Muted.TLabel")
        self._vol = ttk.Label(grid, text="Vol(24h): —", style="Coin.Muted.TLabel")
        self._pct.grid(row=0, column=0, sticky="w"); self._hl.grid(row=1, column=0, sticky="w"); self._vol.grid(row=2, column=0, sticky="w")

        # sparkline
        self._canvas = tk.Canvas(wrap, height=120, bg="#0f1113", highlightthickness=0)
        self._canvas.pack(fill=tk.BOTH, expand=True, padx=6, pady=(6,8))
        self._series = deque(maxlen=240)  # ~ 1-2 мин мини истории
        self._redraw_pending = False

        self._symval = None
        self._stats_thread = None
        self._closing = False

    # public
    def set_symbol(self, symbol: str):
        symbol = (symbol or "").upper()
        self._symval = symbol
        self._sym.configure(text=symbol or "—")
        # reset history
        self._series.clear()
        self._canvas.delete("all")
        # restart stats thread
        self._start_stats_thread()

    def on_quote(self, symbol: str, price: float, pct: float):
        if symbol != self._symval:
            return
        self._price.configure(text=self._fmt_price(price))
        sign = "+" if pct >= 0 else ""
        self._pct.configure(text=f"({sign}{pct:.2f}%)", foreground=THEME["up"] if pct>=0 else THEME["down"])
        # append to series and redraw
        self._series.append(float(price or 0.0))
        if not self._redraw_pending:
            self._redraw_pending = True
            self.after(120, self._redraw)

    def destroy(self):
        self._closing = True
        super().destroy()

    # internals
    def _start_stats_thread(self):
        # stop prev
        if self._stats_thread and self._stats_thread.is_alive():
            self._stats_thread_stop = True
            try: self._stats_thread.join(timeout=0.1)
            except Exception: pass
        # launch new
        self._stats_thread_stop = False
        t = threading.Thread(target=self._stats_worker, daemon=True)
        self._stats_thread = t
        t.start()

    def _stats_worker(self):
        # poll /api/v3/ticker/24hr?symbol=SYMBOL каждые 10 сек
        while not self._stats_thread_stop and not self._closing:
            sym = self._symval
            if not sym:
                time.sleep(1); continue
            try:
                url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={sym}"
                with urllib.request.urlopen(url, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                high = float(data.get("highPrice") or 0.0)
                low  = float(data.get("lowPrice") or 0.0)
                vol  = float(data.get("volume") or 0.0)
                self.after(0, lambda h=high,l=low,v=vol: self._set_stats(h,l,v))
            except Exception:
                pass
            # 10 секунд
            for _ in range(10):
                if self._stats_thread_stop or self._closing: break
                time.sleep(1)

    def _set_stats(self, high, low, vol):
        self._hl.configure(text=f"H/L: {self._fmt_price(high)} / {self._fmt_price(low)}")
        self._vol.configure(text=f"Vol(24h): {vol:,.0f}".replace(",", " "))

    def _redraw(self):
        self._redraw_pending = False
        w = self._canvas.winfo_width() or 10
        h = self._canvas.winfo_height() or 10
        self._canvas.delete("line")
        if len(self._series) < 2:
            return
        mn = min(self._series); mx = max(self._series)
        span = (mx - mn) or 1e-9
        # map series to width
        pts = []
        step = max(1, int(len(self._series) / max(2, w-8)))
        idx = 0
        for i, val in enumerate(list(self._series)[::step]):
            x = int(4 + i * ( (w-8) / max(1, (len(self._series)//step)-1) ))
            y = int(h - 6 - ( (val - mn)/span ) * (h-12))
            pts.append((x,y))
        # draw polyline
        for i in range(1, len(pts)):
            x1,y1 = pts[i-1]; x2,y2 = pts[i]
            self._canvas.create_line(x1,y1,x2,y2, fill="#7ddc84", tags="line")

    def _fmt_price(self, p: float) -> str:
        ap = abs(p)
        if ap == 0:
            return "0"
        if ap < 1:
            return f"{p:.6f}".rstrip("0").rstrip(".")
        if ap < 100:
            return f"{p:.3f}".rstrip("0").rstrip(".")
        return f"{p:.2f}"
