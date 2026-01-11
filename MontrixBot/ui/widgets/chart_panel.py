# ui/widgets/chart_panel.py
# Price + RSI + MACD panel for MontrixBot.
# Preferred: matplotlib (beautiful, themed).
# Fallback: pure Tkinter Canvas (decent, themed) if matplotlib deps are missing.
#
# v2.2.94+ behavior:
# - Supports LIVE mode via on_tick()/append_tick(): incremental updates without clearing axes.
# - Keeps plot_series() for backward compatibility.

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from collections import deque

import tkinter as tk
from tkinter import ttk

_HAS_MPL = False
_MPL_IMPORT_ERROR = ""
try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # type: ignore
    from matplotlib.figure import Figure  # type: ignore

    _HAS_MPL = True
except Exception as e:
    FigureCanvasTkAgg = None  # type: ignore
    Figure = None  # type: ignore
    _HAS_MPL = False
    _MPL_IMPORT_ERROR = f"{type(e).__name__}: {e}"


# -----------------------------------------------------------------------------
# Indicators (pure python)
# -----------------------------------------------------------------------------

def _ema(values: Sequence[float], period: int) -> List[float]:
    vals = [float(v) for v in values]
    if not vals:
        return []
    if period <= 1:
        return list(vals)
    k = 2.0 / (period + 1.0)
    out = [vals[0]]
    for v in vals[1:]:
        out.append(out[-1] + k * (v - out[-1]))
    return out


def _rsi(values: Sequence[float], period: int = 14) -> List[float]:
    vals = [float(v) for v in values]
    n = len(vals)
    if n < 2:
        return []
    if period <= 1:
        return [50.0 for _ in vals]

    gains: List[float] = [0.0]
    losses: List[float] = [0.0]
    for i in range(1, n):
        d = vals[i] - vals[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))

    p = min(period, n - 1)
    avg_gain = sum(gains[1 : p + 1]) / float(p)
    avg_loss = sum(losses[1 : p + 1]) / float(p)

    out: List[float] = []
    for i in range(n):
        if i < p:
            out.append(50.0)
            continue

        if i == p:
            g = avg_gain
            l = avg_loss
        else:
            g = (avg_gain * (p - 1) + gains[i]) / float(p)
            l = (avg_loss * (p - 1) + losses[i]) / float(p)
            avg_gain, avg_loss = g, l

        if l <= 1e-12:
            out.append(100.0)
        else:
            rs = g / l
            out.append(100.0 - (100.0 / (1.0 + rs)))

    return out


def _macd(
    values: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Tuple[List[float], List[float], List[float]]:
    vals = [float(v) for v in values]
    if not vals:
        return [], [], []
    ema_fast = _ema(vals, fast)
    ema_slow = _ema(vals, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = _ema(macd_line, signal)
    hist = [m - s for m, s in zip(macd_line, signal_line)]
    return macd_line, signal_line, hist


def _q(x: float) -> float:
    # reduce float noise for display
    return float(round(float(x), 8))


# -----------------------------------------------------------------------------
# Theme helpers
# -----------------------------------------------------------------------------

def _theme_colors() -> Dict[str, str]:
    # matches MontrixBot dark UI vibe
    return {
        "dark_bg": "#0f1216",
        "card_bg": "#171B21",
        "fg": "#E6EAF2",
        "grid": "#2F3B52",
        "muted": "#9AA3B2",
        "line": "#E6EAF2",
        "accent": "#7AA2F7",
        "warn": "#F2C94C",
    }


# -----------------------------------------------------------------------------
# Matplotlib panel (preferred)
# -----------------------------------------------------------------------------

if _HAS_MPL:

    class ChartPanel(ttk.Frame):
        """Beautiful matplotlib-based chart panel (preferred).

        Supports:
          - plot_series(times, prices): legacy full redraw API
          - on_tick/append_tick: LIVE incremental updates (no cla()).
        """

        def __init__(self, parent: tk.Misc, *, max_points: int = 300):
            super().__init__(parent)

            self._max_points = int(max(10, max_points))
            self._prices: deque[float] = deque(maxlen=self._max_points)
            self._times: deque[int] = deque(maxlen=self._max_points)
            self._tick_counter = 0

            c = _theme_colors()

            self.figure = Figure(figsize=(7.0, 4.0), dpi=100)
            self.ax_price = self.figure.add_subplot(3, 1, 1)
            self.ax_rsi = self.figure.add_subplot(3, 1, 2, sharex=self.ax_price)
            self.ax_macd = self.figure.add_subplot(3, 1, 3, sharex=self.ax_price)

            # theme (static)
            try:
                self.figure.patch.set_facecolor(c["dark_bg"])
                for ax in (self.ax_price, self.ax_rsi, self.ax_macd):
                    ax.set_facecolor(c["card_bg"])
                    ax.grid(True, alpha=0.25)
                    ax.tick_params(colors=c["fg"], labelsize=8)
                    ax.yaxis.label.set_color(c["fg"])
                    ax.xaxis.label.set_color(c["fg"])
                    for spine in ax.spines.values():
                        spine.set_color(c["grid"])
                    ax.title.set_color(c["fg"])
            except Exception:
                pass

            # create artists once (LIVE-friendly)
            self.ax_price.set_title("Price", fontsize=9)
            self.ax_rsi.set_title("RSI", fontsize=9)
            self.ax_macd.set_title("MACD", fontsize=9)

            (self._line_price,) = self.ax_price.plot([], [], linewidth=1.4)
            (self._line_rsi,) = self.ax_rsi.plot([], [], linewidth=1.0)

            self._rsi_h70 = self.ax_rsi.axhline(70, linewidth=0.8, alpha=0.5)
            self._rsi_h30 = self.ax_rsi.axhline(30, linewidth=0.8, alpha=0.5)
            self.ax_rsi.set_ylim(0, 100)

            (self._line_macd,) = self.ax_macd.plot([], [], linewidth=1.0, label="MACD")
            (self._line_signal,) = self.ax_macd.plot([], [], linewidth=1.0, label="Signal")
            self._hist_bars = None  # created on first draw

            self.canvas = FigureCanvasTkAgg(self.figure, master=self)  # type: ignore[arg-type]
            self.canvas.get_tk_widget().pack(fill="both", expand=True)

            # initial layout
            try:
                self.figure.suptitle("MontrixBot — LIVE Chart (ticks=0)", fontsize=10, color=c["fg"])
                self.figure.tight_layout(rect=[0, 0.03, 1, 0.95])
            except Exception:
                pass

        # ----------------------------- public LIVE API

        def on_tick(
            self,
            price: float,
            bid: Optional[float] = None,
            ask: Optional[float] = None,
            ts: Optional[int] = None,
        ) -> None:
            # bid/ask are accepted for future use; currently chart shows mid/price series.
            self.append_tick(price=price, ts=ts)

        def append_tick(self, *, price: float, ts: Optional[int] = None) -> None:
            try:
                p = _q(float(price))
            except Exception:
                return

            if ts is None:
                self._tick_counter += 1
                t = self._tick_counter
            else:
                try:
                    t = int(ts)
                except Exception:
                    self._tick_counter += 1
                    t = self._tick_counter

            self._prices.append(p)
            self._times.append(t)

            self._redraw_live()

        # ----------------------------- legacy API

        def plot_series(self, times: Sequence[int], prices: Sequence[float]) -> None:
            """Legacy full-series API (kept for compatibility)."""
            if not prices:
                self.clear()
                return

            # replace internal buffers
            self._prices.clear()
            self._times.clear()

            # we still draw by index (stable)
            xs = list(range(len(prices)))
            for i, v in enumerate(prices):
                try:
                    self._prices.append(_q(float(v)))
                    self._times.append(int(i))
                except Exception:
                    continue

            self._tick_counter = len(self._prices)
            self._redraw_live()

        def clear(self) -> None:
            self._prices.clear()
            self._times.clear()
            self._tick_counter = 0

            # clear artists (no cla())
            self._line_price.set_data([], [])
            self._line_rsi.set_data([], [])
            self._line_macd.set_data([], [])
            self._line_signal.set_data([], [])
            if self._hist_bars is not None:
                try:
                    for b in self._hist_bars:
                        b.remove()
                except Exception:
                    pass
                self._hist_bars = None

            try:
                c = _theme_colors()
                self.figure.suptitle("MontrixBot — LIVE Chart (ticks=0)", fontsize=10, color=c["fg"])
                self.canvas.draw_idle()
            except Exception:
                pass

        # ----------------------------- internals

        def _redraw_live(self) -> None:
            prices = list(self._prices)
            if not prices:
                self.clear()
                return

            xs = list(range(len(prices)))
            ys = prices

            rsi_vals = _rsi(ys, period=14)
            macd_line, signal_line, hist = _macd(ys)

            # update artists
            self._line_price.set_data(xs, ys)
            self.ax_price.relim()
            self.ax_price.autoscale_view(scalex=True, scaley=True)

            if rsi_vals:
                self._line_rsi.set_data(xs[: len(rsi_vals)], rsi_vals)
            else:
                self._line_rsi.set_data([], [])
            # keep RSI bounds
            self.ax_rsi.set_ylim(0, 100)
            self.ax_rsi.set_xlim(0, max(1, len(xs) - 1))

            self._line_macd.set_data(xs[: len(macd_line)], macd_line if macd_line else [])
            self._line_signal.set_data(xs[: len(signal_line)], signal_line if signal_line else [])

            # histogram bars: recreate lightweight (max 300) — OK
            if self._hist_bars is not None:
                try:
                    for b in self._hist_bars:
                        b.remove()
                except Exception:
                    pass
                self._hist_bars = None
            if hist:
                try:
                    self._hist_bars = self.ax_macd.bar(xs[: len(hist)], hist, alpha=0.3)
                except Exception:
                    self._hist_bars = None

            self.ax_macd.relim()
            self.ax_macd.autoscale_view(scalex=True, scaley=True)

            # title
            try:
                c = _theme_colors()
                ticks = len(ys)
                self.figure.suptitle(
                    f"MontrixBot — LIVE Chart (ticks={ticks})",
                    fontsize=10,
                    color=c["fg"],
                )
            except Exception:
                pass

            # keep layout stable
            try:
                self.figure.tight_layout(rect=[0, 0.03, 1, 0.95])
            except Exception:
                pass

            try:
                self.canvas.draw_idle()
            except Exception:
                pass


# -----------------------------------------------------------------------------
# Tkinter Canvas fallback (decent, themed)
# -----------------------------------------------------------------------------
else:

    class ChartPanel(ttk.Frame):
        """Fallback chart panel without matplotlib (decent Canvas rendering).

        Also supports LIVE mode via on_tick()/append_tick().
        """

        def __init__(self, master: tk.Misc, *, max_points: int = 300):
            super().__init__(master)

            self._max_points = int(max(10, max_points))
            self._prices: deque[float] = deque(maxlen=self._max_points)
            self._tick_counter = 0

            c = _theme_colors()

            self._top = ttk.Frame(self)
            self._mid = ttk.Frame(self)
            self._bot = ttk.Frame(self)
            self._top.pack(fill="both", expand=True)
            self._mid.pack(fill="both", expand=True)
            self._bot.pack(fill="both", expand=True)

            self.lbl_price = ttk.Label(self._top, text=f"Price (fallback) — {_MPL_IMPORT_ERROR}")
            self.lbl_rsi = ttk.Label(self._mid, text="RSI (fallback)")
            self.lbl_macd = ttk.Label(self._bot, text="MACD (fallback)")
            self.lbl_price.pack(anchor="w", padx=8, pady=(8, 0))
            self.lbl_rsi.pack(anchor="w", padx=8, pady=(8, 0))
            self.lbl_macd.pack(anchor="w", padx=8, pady=(8, 0))

            self.cv_price = tk.Canvas(self._top, height=180, highlightthickness=1, background=c["card_bg"])
            self.cv_rsi = tk.Canvas(self._mid, height=140, highlightthickness=1, background=c["card_bg"])
            self.cv_macd = tk.Canvas(self._bot, height=160, highlightthickness=1, background=c["card_bg"])
            self.cv_price.pack(fill="both", expand=True, padx=8, pady=8)
            self.cv_rsi.pack(fill="both", expand=True, padx=8, pady=8)
            self.cv_macd.pack(fill="both", expand=True, padx=8, pady=8)

            for cv in (self.cv_price, self.cv_rsi, self.cv_macd):
                cv.configure(highlightbackground=c["grid"], highlightcolor=c["grid"])

        # ----------------------------- public LIVE API

        def on_tick(
            self,
            price: float,
            bid: Optional[float] = None,
            ask: Optional[float] = None,
            ts: Optional[int] = None,
        ) -> None:
            self.append_tick(price=price, ts=ts)

        def append_tick(self, *, price: float, ts: Optional[int] = None) -> None:
            try:
                p = _q(float(price))
            except Exception:
                return
            self._prices.append(p)
            self._tick_counter += 1
            self._redraw()

        # ----------------------------- legacy API

        def plot_series(self, times: Sequence[int], prices: Sequence[float]) -> None:
            if not prices:
                self.clear()
                return
            self._prices.clear()
            for v in prices[-self._max_points :]:
                try:
                    self._prices.append(_q(float(v)))
                except Exception:
                    continue
            self._redraw()

        def clear(self) -> None:
            self._prices.clear()
            self.cv_price.delete("all")
            self.cv_rsi.delete("all")
            self.cv_macd.delete("all")

        # ----------------------------- drawing helpers

        def _draw_grid(self, cv: tk.Canvas, x0: int, y0: int, x1: int, y1: int) -> None:
            c = _theme_colors()
            for i in range(1, 5):
                x = x0 + (x1 - x0) * i / 5.0
                cv.create_line(x, y0, x, y1, fill=c["grid"])
            for i in range(1, 5):
                y = y0 + (y1 - y0) * i / 5.0
                cv.create_line(x0, y, x1, y, fill=c["grid"])

        def _draw_series(
            self,
            cv: tk.Canvas,
            values: Sequence[float],
            y_min: float,
            y_max: float,
            *,
            extra_hlines: Sequence[float] = (),
            line_width: int = 2,
        ) -> None:
            c = _theme_colors()
            cv.delete("all")

            w = max(10, int(cv.winfo_width()))
            h = max(10, int(cv.winfo_height()))
            if not values:
                cv.create_text(w // 2, h // 2, text="no data", fill=c["muted"])
                return

            vals = [float(v) for v in values]
            n = len(vals)
            if n < 2:
                cv.create_text(w // 2, h // 2, text="too few points", fill=c["muted"])
                return

            if y_max <= y_min:
                vmin = min(vals)
                vmax = max(vals)
            else:
                vmin = y_min
                vmax = y_max

            if abs(vmax - vmin) < 1e-12:
                vmax = vmin + 1.0

            pad = 10
            x0 = pad
            x1 = w - pad
            y0 = pad
            y1 = h - pad

            cv.create_rectangle(x0, y0, x1, y1, outline=c["grid"])
            self._draw_grid(cv, x0, y0, x1, y1)

            for lvl in extra_hlines:
                y = y1 - (y1 - y0) * ((lvl - vmin) / float(vmax - vmin))
                cv.create_line(x0, y, x1, y, fill=c["warn"])

            def sx(i: int) -> float:
                return x0 + (x1 - x0) * (i / float(n - 1))

            def sy(v: float) -> float:
                return y1 - (y1 - y0) * ((v - vmin) / float(vmax - vmin))

            pts: List[float] = []
            for i, v in enumerate(vals):
                pts.extend([sx(i), sy(v)])

            cv.create_line(*pts, width=line_width, fill=c["line"])

        def _draw_macd(self, cv: tk.Canvas, macd_line: Sequence[float], signal_line: Sequence[float]) -> None:
            c = _theme_colors()
            cv.delete("all")
            w = max(10, int(cv.winfo_width()))
            h = max(10, int(cv.winfo_height()))

            if len(macd_line) < 2:
                cv.create_text(w // 2, h // 2, text="no data", fill=c["muted"])
                return

            m = [float(v) for v in macd_line]
            s = [float(v) for v in signal_line] if signal_line else []
            combined = m + s
            vmin = min(combined)
            vmax = max(combined)
            if abs(vmax - vmin) < 1e-12:
                vmax = vmin + 1.0

            pad = 10
            x0 = pad
            x1 = w - pad
            y0 = pad
            y1 = h - pad

            cv.create_rectangle(x0, y0, x1, y1, outline=c["grid"])
            self._draw_grid(cv, x0, y0, x1, y1)

            def sx(i: int, n: int) -> float:
                return x0 + (x1 - x0) * (i / float(max(1, n - 1)))

            def sy(v: float) -> float:
                return y1 - (y1 - y0) * ((v - vmin) / float(vmax - vmin))

            def poly(vals: Sequence[float]) -> List[float]:
                n = len(vals)
                pts: List[float] = []
                for i, v in enumerate(vals):
                    pts.extend([sx(i, n), sy(v)])
                return pts

            cv.create_line(*poly(m), width=2, fill=c["line"])
            if s:
                cv.create_line(*poly(s), width=2, fill=c["accent"])

        def _redraw(self) -> None:
            p = list(self._prices)
            if not p:
                self.clear()
                return

            r = _rsi(p)
            m_line, s_line, _h = _macd(p)

            self._draw_series(self.cv_price, p, y_min=0.0, y_max=0.0)
            self._draw_series(self.cv_rsi, r, y_min=0.0, y_max=100.0, extra_hlines=(30.0, 70.0), line_width=2)
            self._draw_macd(self.cv_macd, m_line, s_line)
