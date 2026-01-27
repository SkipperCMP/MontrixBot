# ui/widgets/chart_panel.py
# Price + RSI + MACD panel for MontrixBot UI.
#
# This file is part of UI-only layer and must remain READ-ONLY (no runtime writes).
#
# Implementation supports matplotlib-based rendering if available. Falls back to Tkinter
# Canvas (decent, themed) if matplotlib deps are missing.
#
#
# NOTE:
# - UI-only: no filesystem reads/writes here.
# - All data must come from controllers/UIAPI.
# - Matplotlib artists must be cleared on redraw to avoid "sticking".

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import math
import time
from datetime import datetime

import tkinter as tk
from tkinter import ttk

import os

# Matplotlib is optional. If missing, we will fallback to Canvas charts.
try:
    import matplotlib

    matplotlib.use("TkAgg")  # safe for Tk
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    from matplotlib.collections import PolyCollection, LineCollection
except Exception:  # pragma: no cover
    FigureCanvasTkAgg = None  # type: ignore
    Figure = None  # type: ignore
    PolyCollection = None  # type: ignore
    LineCollection = None  # type: ignore


# ----------------------------- helpers

def _clamp(v: float, lo: float, hi: float) -> float:
    try:
        return max(lo, min(hi, float(v)))
    except Exception:
        return lo


def _ema(values: Sequence[float], period: int) -> List[float]:
    if not values or period <= 1:
        return []
    k = 2.0 / (period + 1.0)
    out: List[float] = []
    ema_prev: Optional[float] = None
    for v in values:
        try:
            fv = float(v)
        except Exception:
            continue
        if ema_prev is None:
            ema_prev = fv
        else:
            ema_prev = (fv - ema_prev) * k + ema_prev
        out.append(ema_prev)
    return out


def _rsi(values: Sequence[float], period: int = 14) -> List[float]:
    # Simple RSI (Wilder)
    if not values or period <= 1 or len(values) < period + 1:
        return []
    gains: List[float] = []
    losses: List[float] = []
    for i in range(1, len(values)):
        d = values[i] - values[i - 1]
        gains.append(max(0.0, d))
        losses.append(max(0.0, -d))
    # Initial average
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    out: List[float] = []
    # First RSI corresponds to index period
    rs = avg_gain / avg_loss if avg_loss > 0 else math.inf
    rsi = 100.0 - (100.0 / (1.0 + rs))
    out.append(rsi)
    # Subsequent
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss > 0 else math.inf
        rsi = 100.0 - (100.0 / (1.0 + rs))
        out.append(rsi)
    return out


def _macd(values: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[List[float], List[float], List[float]]:
    if not values:
        return ([], [], [])
    ema_fast = _ema(values, fast)
    ema_slow = _ema(values, slow)
    n = min(len(ema_fast), len(ema_slow))
    if n <= 0:
        return ([], [], [])
    macd = [ema_fast[-n + i] - ema_slow[-n + i] for i in range(n)]
    sig = _ema(macd, signal)
    m = min(len(macd), len(sig))
    if m <= 0:
        return (macd, [], [])
    macd2 = macd[-m:]
    sig2 = sig[-m:]
    hist = [macd2[i] - sig2[i] for i in range(m)]
    return (macd2, sig2, hist)


# ----------------------------- canvas fallback (minimal)

class CanvasChart(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0, bg="#0b1020")
        self.canvas.pack(fill="both", expand=True)
        self._title = ""
        self._info = ""

    def set_title(self, title: str) -> None:
        self._title = title
        self._redraw()

    def set_info(self, info: str) -> None:
        self._info = info
        self._redraw()

    def _redraw(self) -> None:
        self.canvas.delete("all")
        w = max(1, int(self.canvas.winfo_width()))
        h = max(1, int(self.canvas.winfo_height()))
        # header
        self.canvas.create_text(10, 10, anchor="nw", text=self._title, fill="#ffffff", font=("Segoe UI", 11, "bold"))
        self.canvas.create_text(10, 30, anchor="nw", text=self._info, fill="#b0b0b0", font=("Segoe UI", 9))
        # placeholder
        self.canvas.create_text(w // 2, h // 2, text="(matplotlib missing)", fill="#ffcc00", font=("Segoe UI", 12, "bold"))


# ----------------------------- main panel

@dataclass
class Theme:
    bg: str = "#0b1020"
    fg: str = "#ffffff"
    grid: str = "#24304d"
    candle_up: str = "#00D18F"
    candle_dn: str = "#FF4D4D"
    wick: str = "#A0A8C0"
    rsi: str = "#6AA9FF"
    macd: str = "#B090FF"
    signal: str = "#FFD56A"
    hist_pos: str = "#00D18F"
    hist_neg: str = "#FF4D4D"


class ChartPanel(ttk.Frame):
        """Beautiful matplotlib-based chart panel (preferred).

        Supports:
         - Candlestick chart (OHLC)
         - EMA20/EMA50 overlays
         - RSI (14)
         - MACD
         - ENTRY/TP/SL levels overlays
         - BUY/SELL trade markers (UI-only)
        """

        def __init__(self, master: tk.Misc, *, theme: Optional[Theme] = None) -> None:
            super().__init__(master)

            def _env_bool(name: str, default: bool) -> bool:
                try:
                    raw = str(os.environ.get(name, "")).strip().lower()
                except Exception:
                    raw = ""
                if raw == "":
                    return bool(default)
                return raw not in ("0", "false", "no", "off")

            self.theme = theme or Theme()
            self._use_mpl = Figure is not None and FigureCanvasTkAgg is not None

            # UI feature flags (READ-ONLY; env only)
            # - MB_UI_CHART_INDICATORS=0 disables BOTH RSI and MACD (fast path)
            # - MB_UI_ENABLE_RSI / MB_UI_ENABLE_MACD override individually
            base_ind = _env_bool("MB_UI_CHART_INDICATORS", True)
            self._enable_rsi = _env_bool("MB_UI_ENABLE_RSI", base_ind)
            self._enable_macd = _env_bool("MB_UI_ENABLE_MACD", base_ind)

            # Cap for legacy tick chart (plot_price_series)
            try:
                self._max_ticks = int(str(os.environ.get("MB_UI_CHART_MAX_TICKS", "")).strip() or "0")
            except Exception:
                self._max_ticks = 0
            if self._max_ticks < 0:
                self._max_ticks = 0

            self._last_draw_ts = 0.0

            # Perf caches / draw scheduling (avoid UI freeze from draw churn)
            self._pending_draw = None   # after_idle id (prevent draw queue explosion)
            self._xtick_cache = None    # (key, xticks, xlabels)
            self._rsi_cache = None      # (key, values)
            self._perf_log_ts = 0.0

            # Data holders
            self._candles: List[dict] = []
            self._prices: List[float] = []

            # UI
            if not self._use_mpl:
                self.fallback = CanvasChart(self)
                self.fallback.pack(fill="both", expand=True)
                return

            self.figure = Figure(figsize=(6, 4), dpi=100)
            self.figure.set_facecolor(self.theme.bg)

            # Layout: 3 rows (price, rsi, macd)
            self.ax_price = self.figure.add_subplot(3, 1, 1)
            self.ax_rsi = self.figure.add_subplot(3, 1, 2)
            self.ax_macd = self.figure.add_subplot(3, 1, 3)

            # Optional: hide indicator panes entirely (still READ-ONLY)
            try:
                self.ax_rsi.set_visible(bool(self._enable_rsi))
            except Exception:
                pass
            try:
                self.ax_macd.set_visible(bool(self._enable_macd))
            except Exception:
                pass

            # Style axes
            for ax in (self.ax_price, self.ax_rsi, self.ax_macd):
                ax.set_facecolor(self.theme.bg)
                ax.tick_params(colors=self.theme.fg, labelsize=8)
                for spine in ax.spines.values():
                    spine.set_color(self.theme.grid)
                ax.grid(True, color=self.theme.grid, alpha=0.25, linewidth=0.8)

            # Performance: axes are managed manually (avoid autoscale churn)
            try:
                self.ax_price.set_autoscale_on(False)
            except Exception:
                pass
            try:
                self.ax_rsi.set_autoscale_on(False)
                self.ax_rsi.set_ylim(0, 100)
            except Exception:
                pass
            try:
                self.ax_macd.set_autoscale_on(False)
            except Exception:
                pass

            self.ax_price.set_title("Candles", color=self.theme.fg, fontsize=10, loc="left")

            self.canvas = FigureCanvasTkAgg(self.figure, master=self)
            self.canvas.get_tk_widget().pack(fill="both", expand=True)

            # Artists storage for cleanup
            self._candle_artists: list = []

            # FAST CANDLES: collections for bodies and wicks (reused; never removed per-frame)
            self._candle_bodies = None  # PolyCollection
            self._candle_wicks = None   # LineCollection

            # Candles overlays (ENTRY / TP / SL) — artists removed on redraw
            self._level_artists: list = []

            # Trade markers (BUY/SELL) — artists removed on redraw
            self._trade_artists: list = []

            # HUD overlays (STALE / SAFE) — artists removed on redraw
            self._hud_artists: list = []

            # Price line (for live / fallback)
            self._line_price, = self.ax_price.plot([], [], linewidth=1.2, alpha=0.85)

            # EMA lines
            self._line_ema20, = self.ax_price.plot([], [], linewidth=1.0, alpha=0.85)
            self._line_ema50, = self.ax_price.plot([], [], linewidth=1.0, alpha=0.85)

            # RSI
            self._line_rsi, = self.ax_rsi.plot([], [], linewidth=1.0, alpha=0.9)
            self._rsi_h30 = self.ax_rsi.axhline(30, linewidth=0.8, alpha=0.5)
            self._rsi_h70 = self.ax_rsi.axhline(70, linewidth=0.8, alpha=0.5)

            # MACD
            self._line_macd, = self.ax_macd.plot([], [], linewidth=1.0, alpha=0.9)
            self._line_signal, = self.ax_macd.plot([], [], linewidth=1.0, alpha=0.9)

            # Legacy histogram bars (list of Rectangle) — kept for fallback only
            self._macd_hist = None

            # FAST MACD histogram: 1 PolyCollection instead of 200+ bar objects
            self._macd_hist_collection = None  # PolyCollection

            # MACD ylim cache (manual + throttled to avoid tick/layout churn)
            self._macd_ylim_cache = None  # type: ignore  # (lo, hi)
            self._last_macd_ylim_ts = 0.0


        def _clear_candles_artists(self) -> None:
            """Clear candle artists.
            - FAST collections: reuse; just clear data + hide (NO remove()).
            - Legacy artists: remove as before.
            """
            # Fast collections: clear data but keep objects
            try:
                if self._candle_bodies is not None:
                    self._candle_bodies.set_verts([])
                    self._candle_bodies.set_visible(False)
            except Exception:
                pass
            try:
                if self._candle_wicks is not None:
                    self._candle_wicks.set_segments([])
                    self._candle_wicks.set_visible(False)
            except Exception:
                pass

            # Legacy: remove individual artists
            if not self._candle_artists:
                return
            try:
                for a in self._candle_artists:
                    try:
                        a.remove()
                    except Exception:
                        pass
            except Exception:
                pass
            self._candle_artists = []

        def _clear_level_artists(self) -> None:
            if not getattr(self, "_level_artists", None):
                return
            try:
                for a in self._level_artists:
                    try:
                        a.remove()
                    except Exception:
                        pass
            except Exception:
                pass
            self._level_artists = []

        def _clear_trade_artists(self) -> None:
            if not getattr(self, "_trade_artists", None):
                return
            try:
                for a in self._trade_artists:
                    try:
                        a.remove()
                    except Exception:
                        pass
            except Exception:
                pass
            self._trade_artists = []

        def _clear_hud_artists(self) -> None:
            if not getattr(self, "_hud_artists", None):
                return
            try:
                for a in self._hud_artists:
                    try:
                        a.remove()
                    except Exception:
                        pass
            except Exception:
                pass
            self._hud_artists = []

        # ----------------------------- UI-only toggles

        def set_indicator_flags(self, *, enable_rsi: bool, enable_macd: bool) -> None:
            """UI-only: enable/disable RSI/MACD without touching runtime state."""
            try:
                self._enable_rsi = bool(enable_rsi)
            except Exception:
                pass
            try:
                self._enable_macd = bool(enable_macd)
            except Exception:
                pass

            # Hide/show panes
            try:
                self.ax_rsi.set_visible(bool(getattr(self, "_enable_rsi", True)))
            except Exception:
                pass
            try:
                self.ax_macd.set_visible(bool(getattr(self, "_enable_macd", True)))
            except Exception:
                pass

            # Clear any previously drawn indicator artists
            try:
                self._line_rsi.set_data([], [])
            except Exception:
                pass
            try:
                self._line_macd.set_data([], [])
                self._line_signal.set_data([], [])
            except Exception:
                pass
            try:
                # Clear legacy bar objects
                if getattr(self, "_macd_hist", None) is not None:
                    for b in self._macd_hist:
                        try:
                            b.remove()
                        except Exception:
                            pass
                    self._macd_hist = None
            except Exception:
                pass

            try:
                # Hide fast histogram collection
                if getattr(self, "_macd_hist_collection", None) is not None:
                    try:
                        self._macd_hist_collection.set_visible(False)
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                # Reset MACD ylim cache (safe; recalculated when enabled)
                self._macd_ylim_cache = None
                self._last_macd_ylim_ts = 0.0
            except Exception:
                pass

            # Redraw (best-effort)
            try:
                if getattr(self, "_use_mpl", False) and hasattr(self, "canvas"):
                    self.canvas.draw_idle()
            except Exception:
                pass

        def set_render_mode(self, mode: str) -> None:
            """UI-only: FULL (candles) vs LIGHT (price line) to reduce matplotlib load."""
            try:
                m = str(mode or "").strip().upper()
            except Exception:
                m = "FULL"
            m = "LIGHT" if m in ("LIGHT", "L") else "FULL"
            try:
                self._render_mode = m
            except Exception:
                pass

            # Visibility: keep it simple; do NOT redefine MIX here (not in this build)
            try:
                if m == "LIGHT":
                    # hide candle collections; show price line
                    if self._candle_bodies is not None:
                        self._candle_bodies.set_visible(False)
                    if self._candle_wicks is not None:
                        self._candle_wicks.set_visible(False)
                    try:
                        self._line_price.set_visible(True)
                    except Exception:
                        pass
                else:
                    # FULL: show collections (if exist); hide price line
                    if self._candle_bodies is not None:
                        self._candle_bodies.set_visible(True)
                    if self._candle_wicks is not None:
                        self._candle_wicks.set_visible(True)
                    try:
                        self._line_price.set_visible(False)
                    except Exception:
                        pass
            except Exception:
                pass

            # Redraw (best-effort)
            try:
                if getattr(self, "_use_mpl", False) and hasattr(self, "canvas"):
                    self.canvas.draw_idle()
            except Exception:
                pass

        # ----------------------------- candles
        def plot_candles(
            self,
            candles: Sequence[dict],
            *,
            levels: Optional[Dict[str, float]] = None,
            trades: Optional[Sequence[dict]] = None,
            debug_meta: Optional[Dict[str, Any]] = None,
        ) -> None:
            if not self._use_mpl:
                try:
                    self.fallback.set_title("Candles")
                    self.fallback.set_info(f"candles={len(candles)}")
                except Exception:
                    pass
                return

            self._candles = list(candles or [])

            # Drop the oldest candle from the visible window (UI-only).
            # This removes the "breathing" artifact on the far-left candle caused by frequent redraw+autoscale.
            drop_left = 1 if len(self._candles) >= 8 else 0
            if drop_left:
                self._candles = self._candles[drop_left:]

            # Smart throttle (bigger payload => slower redraw)
            # IMPORTANT: do NOT queue repeated after() draws (can accumulate and freeze UI)
            now = time.time()
            try:
                n = len(candles)
            except Exception:
                n = 0

            # Adaptive interval: 200+ candles with indicators is heavy on TkAgg
            min_interval = 0.10
            if n >= 200:
                min_interval = 0.25
            elif n >= 120:
                min_interval = 0.18
            elif n >= 60:
                min_interval = 0.14

            if now - self._last_draw_ts < min_interval:
                return
            self._last_draw_ts = now

            # Clear old artists
            self._clear_candles_artists()
            try:
                self._clear_level_artists()
            except Exception:
                pass
            try:
                self._clear_trade_artists()
            except Exception:
                pass
            try:
                self._clear_hud_artists()
            except Exception:
                pass
            try:
                self._line_price.set_data([], [])
            except Exception:
                pass

            # Extract series
            xs: List[float] = []
            opens: List[float] = []
            highs: List[float] = []
            lows: List[float] = []
            closes: List[float] = []
            ts_open_ms_list: List[int] = []

            for i, cndl in enumerate(self._candles):
                try:
                    o = float(cndl.get("o"))
                    h = float(cndl.get("h"))
                    l = float(cndl.get("l"))
                    cl = float(cndl.get("c"))
                except Exception:
                    continue

                # X stays index-based to preserve overlays/trade markers,
                # but labels will be time-based (HH:MM) using ts_open_ms.
                xs.append(float(i))
                opens.append(o)
                highs.append(h)
                lows.append(l)
                closes.append(cl)

                try:
                    ts = int(cndl.get("ts_open_ms") or 0)
                    # normalize seconds -> ms
                    if 0 < ts < 10**11:
                        ts *= 1000
                    ts_open_ms_list.append(ts)
                except Exception:
                    ts_open_ms_list.append(0)

            if not xs:
                # Honest HUD even when no candles were produced (bootstrap pending / no ticks / etc.)
                try:
                    r = ""
                    s = ""
                    try:
                        if debug_meta:
                            r = str(debug_meta.get("reason") or "").strip()
                            s = str(debug_meta.get("source") or "").strip()
                    except Exception:
                        r = ""
                        s = ""

                    if r or s:
                        msg = r if r else "NO_DATA"
                        if s:
                            msg = f"{msg} | {s}"
                        txt = self.ax_price.text(
                            0.01,
                            0.98,
                            msg,
                            transform=self.ax_price.transAxes,
                            ha="left",
                            va="top",
                            fontsize=9,
                            zorder=50,
                            bbox=dict(boxstyle="round,pad=0.25", facecolor="black", alpha=0.40),
                        )
                        self._hud_artists.append(txt)
                except Exception:
                    pass


            # Render mode: FULL (candles) vs LIGHT (price line)
            mode = "FULL"
            try:
                mode = str(getattr(self, "_render_mode", "FULL") or "").strip().upper()
            except Exception:
                mode = "FULL"
            mode = "LIGHT" if mode in ("LIGHT", "L") else "FULL"

            if mode == "LIGHT":
                # Ultra-light: single price line (close) instead of many candle artists
                try:
                    self._line_price.set_data(xs, closes)
                except Exception:
                    pass
            else:
                # FULL: FAST CANDLES via collections (1 PolyCollection + 1 LineCollection)
                width = 0.65

                # Price line should not compete with candles in FULL
                try:
                    self._line_price.set_visible(False)
                except Exception:
                    pass

                # Prepare data for collections
                verts = []         # PolyCollection bodies
                face_colors = []   # body colors
                wick_segments = [] # LineCollection segments (wicks)

                for i in range(len(xs)):
                    x = xs[i]
                    o = opens[i]
                    h = highs[i]
                    l = lows[i]
                    c = closes[i]

                    up = c >= o
                    body_color = self.theme.candle_up if up else self.theme.candle_dn

                    left = x - width / 2.0
                    right = x + width / 2.0
                    bottom = min(o, c)
                    top = max(o, c)
                    height = max(1e-12, top - bottom)

                    # Rectangle polygon (closed)
                    verts.append([
                        (left, bottom),
                        (right, bottom),
                        (right, bottom + height),
                        (left, bottom + height),
                        (left, bottom),
                    ])
                    face_colors.append(body_color)

                    # Wick segment
                    wick_segments.append([(x, l), (x, h)])

                # Create or update collections (no per-candle artists)
                try:
                    if self._candle_bodies is None and PolyCollection is not None:
                        self._candle_bodies = PolyCollection(
                            verts,
                            facecolors=face_colors,
                            edgecolors=face_colors,
                            linewidths=0.5,
                            alpha=0.95,
                            zorder=3,
                        )
                        self.ax_price.add_collection(self._candle_bodies)
                    elif self._candle_bodies is not None:
                        self._candle_bodies.set_verts(verts)
                        self._candle_bodies.set_facecolors(face_colors)
                        self._candle_bodies.set_edgecolors(face_colors)
                        self._candle_bodies.set_visible(True)

                    if self._candle_wicks is None and LineCollection is not None:
                        self._candle_wicks = LineCollection(
                            wick_segments,
                            colors=self.theme.wick,
                            linewidths=1.0,
                            alpha=0.9,
                            zorder=2,
                        )
                        self.ax_price.add_collection(self._candle_wicks)
                    elif self._candle_wicks is not None:
                        self._candle_wicks.set_segments(wick_segments)
                        # one color for all wicks (fast path)
                        try:
                            self._candle_wicks.set_color(self.theme.wick)
                        except Exception:
                            pass
                        self._candle_wicks.set_visible(True)

                except Exception:
                    # Fallback: legacy rendering (rect + wick)
                    width = 0.65
                    for i in range(len(xs)):
                        x = xs[i]
                        o = opens[i]
                        h = highs[i]
                        l = lows[i]
                        c = closes[i]

                        up = c >= o
                        col = self.theme.candle_up if up else self.theme.candle_dn
                        wick_col = self.theme.wick

                        # Wick
                        try:
                            ln = self.ax_price.plot([x, x], [l, h], color=wick_col, linewidth=1.0, alpha=0.9, zorder=2)[0]
                            self._candle_artists.append(ln)
                        except Exception:
                            pass

                        # Body
                        y0 = min(o, c)
                        y1 = max(o, c)
                        try:
                            rect = self.ax_price.add_patch(
                                matplotlib.patches.Rectangle(
                                    (x - width / 2.0, y0),
                                    width,
                                    max(1e-12, y1 - y0),
                                    facecolor=col,
                                    edgecolor=col,
                                    alpha=0.95,
                                    zorder=3,
                                )
                            )
                            self._candle_artists.append(rect)
                        except Exception:
                            pass

            # EMA overlays
            ema20 = _ema(closes, period=20)
            ema50 = _ema(closes, period=50)
            try:
                self._line_ema20.set_data(xs[: len(ema20)], ema20 if ema20 else [])
                self._line_ema50.set_data(xs[: len(ema50)], ema50 if ema50 else [])
            except Exception:
                pass

            # Overlays: ENTRY / TP / SL levels (if provided)
            if levels:
                try:
                    x_right = max(0, len(xs) - 1)

                    # Explicit colors + high zorder to ensure visibility over candles/grid
                    color_map = {
                        "ENTRY": "#FFFFFF",
                        "TP":    "#00D18F",
                        "SL":    "#FF4D4D",
                    }

                    for name, val in (levels or {}).items():
                        try:
                            y = float(val)
                        except Exception:
                            continue
                        if y <= 0:
                            continue

                        c = color_map.get(str(name).upper(), "#FFFFFF")

                        # Horizontal line (ensure on top)
                        try:
                            ln = self.ax_price.axhline(
                                y,
                                linewidth=1.4,
                                alpha=0.95,
                                linestyle="--",
                                color=c,
                                zorder=10,
                            )
                            self._level_artists.append(ln)
                        except Exception:
                            pass

                        # Label near right edge with background for readability
                        try:
                            txt = self.ax_price.text(
                                x_right + 0.25,
                                y,
                                f"{name}: {y:.8f}".rstrip("0").rstrip("."),
                                fontsize=8,
                                alpha=0.95,
                                va="center",
                                color=c,
                                zorder=11,
                                clip_on=False,
                                bbox=dict(
                                    boxstyle="round,pad=0.2",
                                    facecolor="black",
                                    edgecolor=c,
                                    alpha=0.45,
                                ),
                            )
                            self._level_artists.append(txt)
                        except Exception:
                            pass
                except Exception:
                    pass

            # Trade markers (BUY/SELL) (if provided)
            if trades:
                try:
                    for tr in trades:
                        try:
                            x = float(tr.get("x")) - float(drop_left)
                            y = float(tr.get("y"))
                            side = str(tr.get("side") or "").upper().strip()
                        except Exception:
                            continue
                        if y <= 0 or side not in ("BUY", "SELL"):
                            continue
                        # After drop_left shift, ignore markers outside the visible range
                        if x < -0.5 or x > float(len(xs)) + 1.5:
                            continue
                        mk = "^" if side == "BUY" else "v"
                        col = "#00D18F" if side == "BUY" else "#FF4D4D"
                        try:
                            sc = self.ax_price.scatter(
                                [x],
                                [y],
                                marker=mk,
                                s=60,
                                alpha=0.95,
                                color=col,
                                zorder=12,
                            )
                            self._trade_artists.append(sc)
                        except Exception:
                            pass
                except Exception:
                    pass

            # Auto-fit Y with padding (include levels if provided)
            y_min = min(lows) if lows else min(closes)
            y_max = max(highs) if highs else max(closes)

            try:
                if levels:
                    for v in (levels or {}).values():
                        try:
                            fv = float(v)
                        except Exception:
                            continue
                        if fv > 0:
                            y_min = min(y_min, fv)
                            y_max = max(y_max, fv)
            except Exception:
                pass

            pad = (y_max - y_min) * 0.10 if y_max > y_min else max(1e-9, y_max * 0.02)
            self.ax_price.set_ylim(y_min - pad, y_max + pad)

            self.ax_price.set_xlim(-1.0, float(len(xs)) + 2.0)

            # Time-based X axis labels (HH:MM) using ts_open_ms
            # PERF: cache tick labels; set_xticks/set_xticklabels is expensive in TkAgg
            try:
                n = len(xs)
                if n > 0 and ts_open_ms_list and len(ts_open_ms_list) == n:
                    # choose step so we don't spam labels
                    if n <= 12:
                        step = 1
                    elif n <= 30:
                        step = 2
                    elif n <= 60:
                        step = 5
                    else:
                        step = 10

                    # Cache key: only recompute when the visible time window changes
                    ts0 = 0
                    ts_last = 0
                    try:
                        ts0 = int(ts_open_ms_list[0] or 0)
                    except Exception:
                        ts0 = 0
                    try:
                        ts_last = int(ts_open_ms_list[-1] or 0)
                    except Exception:
                        ts_last = 0

                    key = (n, step, ts0, ts_last)

                    cached = getattr(self, "_xtick_cache", None)
                    if cached and len(cached) == 3 and cached[0] == key:
                        xticks = cached[1]
                        xlabels = cached[2]
                    else:
                        xticks = []
                        xlabels = []
                        for i in range(0, n, step):
                            try:
                                ts_ms = int(ts_open_ms_list[i] or 0)
                            except Exception:
                                ts_ms = 0
                            if ts_ms <= 0:
                                continue
                            try:
                                dt = datetime.fromtimestamp(ts_ms / 1000.0)
                                lab = dt.strftime("%H:%M")
                            except Exception:
                                lab = ""
                            xticks.append(float(i))
                            xlabels.append(lab)
                        try:
                            self._xtick_cache = (key, xticks, xlabels)
                        except Exception:
                            pass

                    # apply to all axes for consistency
                    for ax in (self.ax_price, self.ax_rsi, self.ax_macd):
                        try:
                            ax.set_xticks(xticks)
                            ax.set_xticklabels(xlabels, fontsize=8, color=self.theme.fg)
                        except Exception:
                            pass
            except Exception:
                pass


            # RSI + MACD (feature-flagged to reduce UI load)
            try:
                if getattr(self, "_enable_rsi", True):
                    # PERF: cache RSI when closes window unchanged
                    try:
                        tail = closes[-40:] if len(closes) >= 40 else closes
                        rsi_key = (len(closes), float(tail[0]) if tail else 0.0, float(tail[-1]) if tail else 0.0, tuple(round(x, 10) for x in tail))
                    except Exception:
                        rsi_key = None

                    cached = getattr(self, "_rsi_cache", None)
                    if cached and len(cached) == 2 and cached[0] == rsi_key:
                        rsi_vals = cached[1]
                    else:
                        rsi_vals = _rsi(closes, period=14)
                        try:
                            self._rsi_cache = (rsi_key, rsi_vals)
                        except Exception:
                            pass

                    if rsi_vals:
                        xs_rsi = xs[-len(rsi_vals) :]
                        self._line_rsi.set_data(xs_rsi, rsi_vals)
                        try:
                            self.ax_rsi.set_ylim(0, 100)
                        except Exception:
                            pass
                    else:
                        self._line_rsi.set_data([], [])
                else:
                    # fast path: no compute
                    self._line_rsi.set_data([], [])
            except Exception:
                pass

            try:
                if getattr(self, "_enable_macd", True):
                    macd_line, signal_line, hist = _macd(closes)
                    if macd_line and signal_line:
                        xs_macd = xs[-len(macd_line) :]
                        self._line_macd.set_data(xs_macd, macd_line)
                        self._line_signal.set_data(xs_macd, signal_line)

                        # hist bars (FAST via PolyCollection): 1 object instead of 200+ bar objects
                        try:
                            if mode == "LIGHT":
                                # In LIGHT mode skip histogram entirely
                                try:
                                    if self._macd_hist_collection is not None:
                                        self._macd_hist_collection.set_visible(False)
                                except Exception:
                                    pass
                                # remove legacy bars if any
                                try:
                                    if self._macd_hist is not None:
                                        for b in self._macd_hist:
                                            try:
                                                b.remove()
                                            except Exception:
                                                pass
                                    self._macd_hist = None
                                except Exception:
                                    pass
                            else:
                                # Build histogram rectangles as polygons
                                width = 0.65
                                verts = []
                                colors = []
                                for i, h in enumerate(hist):
                                    x = xs_macd[i]
                                    left = x - width / 2.0
                                    right = x + width / 2.0
                                    bottom = 0.0
                                    top = float(h)

                                    verts.append([
                                        (left, bottom),
                                        (right, bottom),
                                        (right, top),
                                        (left, top),
                                        (left, bottom),
                                    ])
                                    colors.append(self.theme.hist_pos if top >= 0 else self.theme.hist_neg)

                                # Create/update collection
                                if self._macd_hist_collection is None and PolyCollection is not None:
                                    self._macd_hist_collection = PolyCollection(
                                        verts,
                                        facecolors=colors,
                                        edgecolors=colors,
                                        linewidths=0.0,
                                        alpha=0.65,
                                        zorder=1,
                                    )
                                    self.ax_macd.add_collection(self._macd_hist_collection)
                                elif self._macd_hist_collection is not None:
                                    self._macd_hist_collection.set_verts(verts)
                                    self._macd_hist_collection.set_facecolors(colors)
                                    self._macd_hist_collection.set_edgecolors(colors)
                                    self._macd_hist_collection.set_visible(True)

                                # remove legacy bars if any
                                try:
                                    if self._macd_hist is not None:
                                        for b in self._macd_hist:
                                            try:
                                                b.remove()
                                            except Exception:
                                                pass
                                    self._macd_hist = None
                                except Exception:
                                    pass

                                # Manual MACD ylim (throttled): include macd/signal/hist
                                try:
                                    lo = min(min(macd_line), min(signal_line), min(hist))
                                    hi = max(max(macd_line), max(signal_line), max(hist))
                                    span = hi - lo
                                    pad = span * 0.15 if span > 0 else max(1e-6, abs(hi) * 0.20)

                                    want_lo = float(lo - pad)
                                    want_hi = float(hi + pad)

                                    now2 = time.time()
                                    cur = getattr(self, "_macd_ylim_cache", None)
                                    cur_lo = None
                                    cur_hi = None
                                    try:
                                        if cur and len(cur) == 2:
                                            cur_lo = float(cur[0])
                                            cur_hi = float(cur[1])
                                    except Exception:
                                        cur_lo = None
                                        cur_hi = None

                                    must = False
                                    try:
                                        if cur_lo is None or cur_hi is None:
                                            must = True
                                        elif want_lo < cur_lo or want_hi > cur_hi:
                                            must = True
                                        elif now2 - float(getattr(self, "_last_macd_ylim_ts", 0.0) or 0.0) > 0.80:
                                            must = True
                                    except Exception:
                                        must = True

                                    if must:
                                        try:
                                            self.ax_macd.set_ylim(want_lo, want_hi)
                                        except Exception:
                                            pass
                                        try:
                                            self._macd_ylim_cache = (want_lo, want_hi)
                                            self._last_macd_ylim_ts = now2
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                        except Exception:
                            # Fallback to legacy bar() if PolyCollection fails
                            try:
                                colors = [self.theme.hist_pos if h >= 0 else self.theme.hist_neg for h in hist]
                                if getattr(self, "_macd_hist", None) is not None and len(self._macd_hist) == len(hist):
                                    for b, h, c in zip(self._macd_hist, hist, colors):
                                        try:
                                            b.set_height(h)
                                            b.set_color(c)
                                        except Exception:
                                            pass
                                else:
                                    try:
                                        if self._macd_hist is not None:
                                            for b in self._macd_hist:
                                                try:
                                                    b.remove()
                                                except Exception:
                                                    pass
                                    except Exception:
                                        pass
                                    container = self.ax_macd.bar(xs_macd, hist, width=0.65, alpha=0.65, color=colors)
                                    self._macd_hist = list(container)
                            except Exception:
                                pass
                    else:
                        self._line_macd.set_data([], [])
                        self._line_signal.set_data([], [])
                else:
                    # fast path: no compute + clear previous bars
                    self._line_macd.set_data([], [])
                    self._line_signal.set_data([], [])
                    try:
                        if self._macd_hist is not None:
                            for b in self._macd_hist:
                                try:
                                    b.remove()
                                except Exception:
                                    pass
                            self._macd_hist = None
                    except Exception:
                        pass
            except Exception:
                pass

            # Honest HUD (bootstrap / source / reason) — top-right
            try:
                r = ""
                s = ""
                try:
                    if debug_meta:
                        r = str(debug_meta.get("reason") or "").strip()
                        s = str(debug_meta.get("source") or "").strip()
                except Exception:
                    r = ""
                    s = ""

                if r or s:
                    msg = r if r else "OK"
                    if s:
                        msg = f"{msg} | {s}"
                    txt = self.ax_price.text(
                        0.99,
                        0.98,
                        msg,
                        transform=self.ax_price.transAxes,
                        ha="right",
                        va="top",
                        fontsize=9,
                        zorder=50,
                        bbox=dict(boxstyle="round,pad=0.25", facecolor="black", alpha=0.35),
                    )
                    self._hud_artists.append(txt)
            except Exception:
                pass

            # Stale detector (UI-only): if last candle is too old vs timeframe, show SAFE overlay
            is_stale = False
            stale_age_ms = 0
            try:
                now_ms = int(time.time() * 1000)
                ts_last = 0
                try:
                    # prefer debug_meta (post-cleanup)
                    if debug_meta and int(debug_meta.get("ts_last") or 0) > 0:
                        ts_last = int(debug_meta.get("ts_last") or 0)
                except Exception:
                    ts_last = 0

                if ts_last <= 0 and ts_open_ms_list:
                    try:
                        ts_last = int(ts_open_ms_list[-1] or 0)
                    except Exception:
                        ts_last = 0

                tf_ms = 0
                try:
                    if debug_meta and int(debug_meta.get("tf_ms") or 0) > 0:
                        tf_ms = int(debug_meta.get("tf_ms") or 0)
                except Exception:
                    tf_ms = 0

                # estimate tf_ms from timestamps if not provided
                if tf_ms <= 0 and ts_open_ms_list and len(ts_open_ms_list) >= 2:
                    deltas = []
                    prev = None
                    for t in ts_open_ms_list:
                        try:
                            tt = int(t or 0)
                        except Exception:
                            continue
                        if tt <= 0:
                            continue
                        if prev is not None:
                            d = tt - prev
                            if d > 0:
                                deltas.append(d)
                        prev = tt
                    if deltas:
                        deltas.sort()
                        tf_ms = int(deltas[len(deltas) // 2])

                if ts_last > 0 and tf_ms > 0:
                    stale_age_ms = max(0, int(now_ms - ts_last))
                    # stale threshold: 2 candles behind (min 120s, max not limited)
                    thr = max(int(2 * tf_ms), 120_000)
                    if stale_age_ms > thr:
                        is_stale = True
            except Exception:
                is_stale = False
                stale_age_ms = 0

            if is_stale:
                try:
                    age_s = int(stale_age_ms // 1000)
                    txt = self.ax_price.text(
                        0.01,
                        0.98,
                        f"SAFE: STALE CANDLES ({age_s}s)",
                        transform=self.ax_price.transAxes,
                        ha="left",
                        va="top",
                        fontsize=9,
                        color="#FF4D4D",
                        zorder=50,
                        bbox=dict(
                            boxstyle="round,pad=0.25",
                            facecolor="black",
                            edgecolor="#FF4D4D",
                            alpha=0.55,
                        ),
                    )
                    self._hud_artists.append(txt)
                except Exception:
                    pass

            # Title
            try:
                c = {"fg": self.theme.fg}
            except Exception:
                c = {"fg": "#ffffff"}

            try:
                title = f"MontrixBot — Candles (n={len(candles)})"
                try:
                    if is_stale:
                        title += f" | STALE={int(stale_age_ms // 1000)}s"
                except Exception:
                    pass
                if debug_meta:
                    try:
                        title += (
                            f" | ts0={debug_meta.get('ts0')}"
                            f" ts_last={debug_meta.get('ts_last')}"
                            f" dupes={debug_meta.get('dupes')}"
                        )
                    except Exception:
                        pass

                self.figure.suptitle(
                    title,
                    fontsize=10,
                    color=c["fg"],
                )
            except Exception:
                pass
            # PERF: prevent draw queue accumulation (TkAgg can freeze if draw_idle is spammed)
            try:
                if getattr(self, "_pending_draw", None) is not None:
                    try:
                        self.after_cancel(self._pending_draw)
                    except Exception:
                        pass
                self._pending_draw = self.after_idle(self.canvas.draw_idle)
            except Exception:
                try:
                    self.canvas.draw_idle()
                except Exception:
                    pass

        # ----------------------------- legacy API

        def plot_price_series(self, ts_ms: Sequence[int], prices: Sequence[float], *, title: str = "LIVE") -> None:
            """Legacy: plot live price series (tick chart)."""
            if not self._use_mpl:
                try:
                    self.fallback.set_title(title)
                    self.fallback.set_info(f"points={len(prices)}")
                except Exception:
                    pass
                return

            # store (optionally capped)
            self._prices = list(prices or [])

            try:
                cap = int(getattr(self, "_max_ticks", 0) or 0)
            except Exception:
                cap = 0

            if cap and cap > 0 and len(self._prices) > cap:
                self._prices = self._prices[-cap:]
                try:
                    ts_ms = list(ts_ms or [])
                    if len(ts_ms) > cap:
                        ts_ms = ts_ms[-cap:]
                except Exception:
                    pass

            xs = list(range(len(self._prices)))
            ys = self._prices

            # clear and draw
            self._clear_candles_artists()
            try:
                self._clear_level_artists()
            except Exception:
                pass
            try:
                self._clear_trade_artists()
            except Exception:
                pass

            self._line_price.set_data(xs, ys)
            self.ax_price.relim()
            self.ax_price.autoscale_view(scalex=True, scaley=True)
            self.ax_price.set_title(title, color=self.theme.fg, fontsize=10, loc="left")
            try:
                self.canvas.draw_idle()
            except Exception:
                pass

        def clear(self) -> None:
            if not self._use_mpl:
                try:
                    self.fallback.set_title("")
                    self.fallback.set_info("")
                except Exception:
                    pass
                return

            self._clear_candles_artists()
            try:
                self._clear_level_artists()
            except Exception:
                pass
            try:
                self._clear_trade_artists()
            except Exception:
                pass

            self._line_rsi.set_data([], [])
            self._line_macd.set_data([], [])
            self._line_signal.set_data([], [])
            self._line_ema20.set_data([], [])
            self._line_ema50.set_data([], [])
            self._line_price.set_data([], [])

            try:
                # Clear legacy bar objects
                if self._macd_hist is not None:
                    for b in self._macd_hist:
                        try:
                            b.remove()
                        except Exception:
                            pass
                    self._macd_hist = None
            except Exception:
                pass

            try:
                # Hide fast histogram collection (reuse later)
                if getattr(self, "_macd_hist_collection", None) is not None:
                    try:
                        self._macd_hist_collection.set_verts([])
                    except Exception:
                        pass
                    try:
                        self._macd_hist_collection.set_visible(False)
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                self._macd_ylim_cache = None
                self._last_macd_ylim_ts = 0.0
            except Exception:
                pass

            try:
                self.canvas.draw_idle()
            except Exception:
                pass

        def _redraw_live(self, prices: Sequence[float]) -> None:
            """Internal: update live price series without full reset."""
            if not self._use_mpl:
                try:
                    self.fallback.set_title("LIVE")
                    self.fallback.set_info(f"points={len(prices)}")
                except Exception:
                    pass
                return

            self._prices = list(prices or [])
            xs = list(range(len(self._prices)))
            ys = self._prices

            rsi_vals = _rsi(ys, period=14)
            macd_line, signal_line, hist = _macd(ys)

            # update artists
            try:
                self._clear_candles_artists()
            except Exception:
                pass
            try:
                self._clear_level_artists()
            except Exception:
                pass
            try:
                self._clear_trade_artists()
            except Exception:
                pass
            try:
                self._line_ema20.set_data([], [])
                self._line_ema50.set_data([], [])
            except Exception:
                pass

            self._line_price.set_data(xs, ys)
            self.ax_price.relim()
            self.ax_price.autoscale_view(scalex=True, scaley=True)

            if rsi_vals:
                self._line_rsi.set_data(xs[: len(rsi_vals)], rsi_vals)
            else:
                self._line_rsi.set_data([], [])

            if macd_line and signal_line:
                xs_macd = xs[-len(macd_line) :]
                self._line_macd.set_data(xs_macd, macd_line)
                self._line_signal.set_data(xs_macd, signal_line)

                # hist bars (FAST via PolyCollection)
                try:
                    width = 0.65
                    verts = []
                    colors = []
                    for i, h in enumerate(hist):
                        x = xs_macd[i]
                        left = x - width / 2.0
                        right = x + width / 2.0
                        bottom = 0.0
                        top = float(h)
                        verts.append([
                            (left, bottom),
                            (right, bottom),
                            (right, top),
                            (left, top),
                            (left, bottom),
                        ])
                        colors.append(self.theme.hist_pos if top >= 0 else self.theme.hist_neg)

                    if self._macd_hist_collection is None and PolyCollection is not None:
                        self._macd_hist_collection = PolyCollection(
                            verts,
                            facecolors=colors,
                            edgecolors=colors,
                            linewidths=0.0,
                            alpha=0.65,
                            zorder=1,
                        )
                        self.ax_macd.add_collection(self._macd_hist_collection)
                    elif self._macd_hist_collection is not None:
                        self._macd_hist_collection.set_verts(verts)
                        self._macd_hist_collection.set_facecolors(colors)
                        self._macd_hist_collection.set_edgecolors(colors)
                        self._macd_hist_collection.set_visible(True)

                    # remove legacy bars if any
                    try:
                        if self._macd_hist is not None:
                            for b in self._macd_hist:
                                try:
                                    b.remove()
                                except Exception:
                                    pass
                        self._macd_hist = None
                    except Exception:
                        pass

                    # Manual MACD ylim (throttled)
                    try:
                        lo = min(min(macd_line), min(signal_line), min(hist))
                        hi = max(max(macd_line), max(signal_line), max(hist))
                        span = hi - lo
                        pad = span * 0.15 if span > 0 else max(1e-6, abs(hi) * 0.20)
                        want_lo = float(lo - pad)
                        want_hi = float(hi + pad)

                        now2 = time.time()
                        cur = getattr(self, "_macd_ylim_cache", None)
                        cur_lo = None
                        cur_hi = None
                        try:
                            if cur and len(cur) == 2:
                                cur_lo = float(cur[0])
                                cur_hi = float(cur[1])
                        except Exception:
                            cur_lo = None
                            cur_hi = None

                        must = False
                        try:
                            if cur_lo is None or cur_hi is None:
                                must = True
                            elif want_lo < cur_lo or want_hi > cur_hi:
                                must = True
                            elif now2 - float(getattr(self, "_last_macd_ylim_ts", 0.0) or 0.0) > 0.80:
                                must = True
                        except Exception:
                            must = True

                        if must:
                            try:
                                self.ax_macd.set_ylim(want_lo, want_hi)
                            except Exception:
                                pass
                            try:
                                self._macd_ylim_cache = (want_lo, want_hi)
                                self._last_macd_ylim_ts = now2
                            except Exception:
                                pass
                    except Exception:
                        pass
                except Exception:
                    # Fallback to legacy per-bar redraw
                    try:
                        if self._macd_hist is not None:
                            for b in self._macd_hist:
                                try:
                                    b.remove()
                                except Exception:
                                    pass
                            self._macd_hist = None
                    except Exception:
                        pass
                    try:
                        bars = []
                        for i in range(len(hist)):
                            h = hist[i]
                            x = xs_macd[i]
                            col = self.theme.hist_pos if h >= 0 else self.theme.hist_neg
                            bar = self.ax_macd.bar([x], [h], width=0.65, alpha=0.65, color=col)
                            for b in bar:
                                bars.append(b)
                        self._macd_hist = bars
                    except Exception:
                        pass
            else:
                self._line_macd.set_data([], [])
                self._line_signal.set_data([], [])

            try:
                self.canvas.draw_idle()
            except Exception:
                pass
