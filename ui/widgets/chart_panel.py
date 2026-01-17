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

# Matplotlib is optional. If missing, we will fallback to Canvas charts.
try:
    import matplotlib

    matplotlib.use("TkAgg")  # safe for Tk
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
except Exception:  # pragma: no cover
    FigureCanvasTkAgg = None  # type: ignore
    Figure = None  # type: ignore


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

            self.theme = theme or Theme()
            self._use_mpl = Figure is not None and FigureCanvasTkAgg is not None

            self._last_draw_ts = 0.0

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

            # Style axes
            for ax in (self.ax_price, self.ax_rsi, self.ax_macd):
                ax.set_facecolor(self.theme.bg)
                ax.tick_params(colors=self.theme.fg, labelsize=8)
                for spine in ax.spines.values():
                    spine.set_color(self.theme.grid)
                ax.grid(True, color=self.theme.grid, alpha=0.25, linewidth=0.8)

            self.ax_price.set_title("Candles", color=self.theme.fg, fontsize=10, loc="left")

            self.canvas = FigureCanvasTkAgg(self.figure, master=self)
            self.canvas.get_tk_widget().pack(fill="both", expand=True)

            # Artists storage for cleanup
            self._candle_artists: list = []

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
            self._macd_hist = None

        def _clear_candles_artists(self) -> None:
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

            # Throttle redraw
            now = time.time()
            if now - self._last_draw_ts < 0.05:
                # schedule async draw
                try:
                    self.after(50, lambda: self.plot_candles(self._candles, levels=levels, trades=trades))
                except Exception:
                    pass
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
                try:
                    self.canvas.draw_idle()
                except Exception:
                    pass
                return

            # Plot candles manually (rect + wick)
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

                    # apply to all axes for consistency
                    for ax in (self.ax_price, self.ax_rsi, self.ax_macd):
                        try:
                            ax.set_xticks(xticks)
                            ax.set_xticklabels(xlabels, fontsize=8, color=self.theme.fg)
                        except Exception:
                            pass
            except Exception:
                pass

            # RSI + MACD
            try:
                rsi_vals = _rsi(closes, period=14)
                macd_line, signal_line, hist = _macd(closes)

                if rsi_vals:
                    xs_rsi = xs[-len(rsi_vals) :]
                    self._line_rsi.set_data(xs_rsi, rsi_vals)
                    self.ax_rsi.set_ylim(0, 100)
                else:
                    self._line_rsi.set_data([], [])

                if macd_line and signal_line:
                    xs_macd = xs[-len(macd_line) :]
                    self._line_macd.set_data(xs_macd, macd_line)
                    self._line_signal.set_data(xs_macd, signal_line)

                    # hist bars (clear / redraw)
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
                            # bar is a container
                            for b in bar:
                                bars.append(b)
                        self._macd_hist = bars
                    except Exception:
                        pass
                else:
                    self._line_macd.set_data([], [])
                    self._line_signal.set_data([], [])
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

            # store
            self._prices = list(prices or [])

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

                # hist bars (clear / redraw)
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
