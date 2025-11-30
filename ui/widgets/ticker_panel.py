from __future__ import annotations
import tkinter as tk
from tkinter import ttk
import time

THEME = {
    "bg": "#151719",
    "tile": "#1d2023",
    "tile_hover": "#24282c",
    "text": "#d7dde4",
    "muted": "#9aa3ad",
    "up": "#7ddc84",
    "down": "#ff7a7a",
    "sep": "#0f1113",
    "badge": "#2a2f34",
}

# минимальный относительный порог, чтобы не мигать на шумах тика
DELTA_EPS = 0.00015  # 0.015% (tick-to-tick)

class LiveTickerPanel(ttk.Frame):
    def __init__(self, master, on_symbol_click=None, max_visible=12):
        super().__init__(master)
        self.on_symbol_click = on_symbol_click
        self.max_visible = max_visible
        self.configure(style="TickerPanel.TFrame")

        self._items = {}
        self._order = []
        self._more_label = None
        style = ttk.Style(self)
        try: style.theme_use(style.theme_use())
        except Exception: pass
        style.configure("TickerPanel.TFrame", background=THEME["bg"])
        style.configure("Ticker.Tile.TFrame", background=THEME["tile"])
        style.map("Ticker.Tile.TFrame", background=[("active", THEME["tile_hover"])])
        style.configure("Ticker.Symbol.TLabel", background=THEME["tile"], foreground=THEME["text"])
        style.configure("Ticker.Price.TLabel", background=THEME["tile"], foreground=THEME["text"])
        style.configure("Ticker.Pct.TLabel", background=THEME["tile"], foreground=THEME["muted"])
        style.configure("Ticker.Badge.TLabel", background=THEME["badge"], foreground=THEME["text"])

        self._wrap = ttk.Frame(self, style="TickerPanel.TFrame"); self._wrap.pack(fill=tk.X, padx=6, pady=6)
        self._tiles = ttk.Frame(self._wrap, style="TickerPanel.TFrame"); self._tiles.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._tip = None

    # --- public API
    def set_tickers(self, rows):
        syms = [r.get("symbol","").upper() for r in rows if r.get("symbol")]
        for s in syms:
            if s not in self._order:
                self._order.append(s)
        for s in list(self._order):
            if s not in syms:
                self._order.remove(s); self._remove_tile(s)
        for r in rows:
            s=r.get("symbol","").upper(); self._ensure_tile(s)
            self._render_quote(s, float(r.get("price") or 0.0), float(r.get("pct") or 0.0), initial=True)
        self._relayout()

    def update_quote(self, symbol, price, pct):
        s = (symbol or "").upper()
        if not s: return
        if s not in self._order:
            self._order.append(s); self._ensure_tile(s)
        self._render_quote(s, float(price or 0.0), float(pct or 0.0), initial=False)
        self._relayout()

    # --- internals
    def _ensure_tile(self, s):
        if s in self._items: return
        root = ttk.Frame(self._tiles, style="Ticker.Tile.TFrame")
        root.bind("<Button-1>", lambda e, sym=s: self._click(sym))
        sym_lbl = ttk.Label(root, text=s.replace("USDT",""), style="Ticker.Symbol.TLabel")
        price_lbl = ttk.Label(root, text="0", style="Ticker.Price.TLabel", width=9, anchor="e")
        pct_lbl = ttk.Label(root, text="(+0.00%)", style="Ticker.Pct.TLabel")
        arrow_lbl = ttk.Label(root, text="•", style="Ticker.Pct.TLabel")
        sym_lbl.pack(side=tk.LEFT, padx=(8,6)); price_lbl.pack(side=tk.LEFT)
        pct_lbl.pack(side=tk.LEFT, padx=(6,2)); arrow_lbl.pack(side=tk.LEFT, padx=(4,8))
        self._items[s] = {"root":root,"sym":sym_lbl,"price":price_lbl,"pct":pct_lbl,"arrow":arrow_lbl,"last_price":None}

    def _remove_tile(self, s):
        w=self._items.pop(s,None)
        if w:
            try: w["root"].destroy()
            except Exception: pass

    def _relayout(self):
        for idx,s in enumerate(self._order):
            w=self._items.get(s); 
            if not w: continue
            w["root"].pack_forget()
            if idx < self.max_visible:
                w["root"].pack(side=tk.LEFT, padx=4)
        hidden = max(0, len(self._order)-self.max_visible)
        if hasattr(self, "_more"): 
            try: self._more.destroy()
            except Exception: pass
            self._more=None
        if hidden>0:
            self._more = ttk.Label(self._tiles, text=f"+{hidden} more", style="Ticker.Badge.TLabel"); self._more.pack(side=tk.LEFT, padx=6)

    def _render_quote(self, s, price, pct, initial=False):
        w=self._items.get(s); 
        if not w: return
        # text update
        w["price"].configure(text=self._fmt_price(price))
        sign = "+" if pct>=0 else ""
        w["pct"].configure(text=f"({sign}{pct:.2f}%)")
        lp = w["last_price"]

        # determine direction by tick-to-tick delta, not by 24h pct
        direction = 0
        if lp is not None:
            rel = 0 if lp==0 else abs((price-lp)/lp)
            if rel > DELTA_EPS:
                direction = 1 if price>lp else -1
        # arrows + color
        if direction>0:
            w["arrow"].configure(text="▲", foreground=THEME["up"])
            self._fade(w["root"], up=True)
            self._pulse(w["price"], up=True)
        elif direction<0:
            w["arrow"].configure(text="▼", foreground=THEME["down"])
            self._fade(w["root"], up=False)
            self._pulse(w["price"], up=False)
        else:
            w["arrow"].configure(text="•", foreground=THEME["muted"])

        w["last_price"]=price

    def _fmt_price(self, p: float)->str:
        ap=abs(p)
        if ap==0: return "0"
        if ap<1: return f"{p:.6f}".rstrip("0").rstrip(".")
        if ap<100: return f"{p:.3f}".rstrip("0").rstrip(".")
        return f"{p:.2f}"

    # visuals
    def _fade(self, widget, up: bool, steps:int=6):
        start = self.winfo_rgb(THEME["tile"])
        tint = THEME["up"] if up else THEME["down"]
        end = self.winfo_rgb(tint)
        end = tuple(int(start[i]*0.75 + end[i]*0.25) for i in range(3))
        def mix(a,b,t): return int(a + (b-a)*t)
        def step(i=0):
            if i>steps:
                try: widget.configure(style="Ticker.Tile.TFrame")
                except Exception: pass
                return
            k=i/steps
            rgb="#%04x%04x%04x"%(mix(start[0],end[0],k),mix(start[1],end[1],k),mix(start[2],end[2],k))
            name=f"__Fade{i}.TFrame"; st=ttk.Style(widget)
            try:
                st.configure(name, background=rgb); widget.configure(style=name)
            except Exception: pass
            widget.after(30, lambda: step(i+1))
        step()

    def _pulse(self, label, up:bool):
        base=THEME["text"]; tint=THEME["up"] if up else THEME["down"]
        st=ttk.Style(label)
        try:
            st.configure("__P1.TLabel", foreground=tint); label.configure(style="__P1.TLabel")
            label.after(80, lambda: (st.configure("Ticker.Price.TLabel", foreground=base), label.configure(style="Ticker.Price.TLabel")))
        except Exception: pass

    def _click(self, s):
        if callable(self.on_symbol_click):
            try: self.on_symbol_click(s)
            except Exception: pass
