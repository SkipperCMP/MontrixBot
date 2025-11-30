# ui/widgets/chart_panel.py
# Price + RSI + MACD panel for MontrixBot.

from __future__ import annotations

from typing import List, Sequence, Tuple

import tkinter as tk
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


def _ema(values: Sequence[float], period: int) -> List[float]:
    """Простейшая EMA для MACD."""
    vals = [float(v) for v in values]
    n = len(vals)
    if n == 0 or period <= 1:
        return vals
    alpha = 2.0 / (period + 1.0)
    ema_vals: List[float] = []
    prev = vals[0]
    for v in vals:
        prev = alpha * v + (1.0 - alpha) * prev
        ema_vals.append(prev)
    return ema_vals


def _rsi(values: Sequence[float], period: int = 14) -> List[float]:
    vals = [float(v) for v in values]
    n = len(vals)
    if n == 0 or period <= 1:
        return [50.0 for _ in vals]

    gains: List[float] = [0.0]
    losses: List[float] = [0.0]
    for i in range(1, n):
        diff = vals[i] - vals[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))

    avg_gain = sum(gains[1:period + 1]) / max(period, 1)
    avg_loss = sum(losses[1:period + 1]) / max(period, 1)

    rsi_vals: List[float] = []
    for i in range(n):
        if i < period:
            rsi_vals.append(50.0)
            continue
        if i == period:
            g = avg_gain
            l = avg_loss
        else:
            g = (avg_gain * (period - 1) + gains[i]) / period
            l = (avg_loss * (period - 1) + losses[i]) / period
            avg_gain, avg_loss = g, l
        if l == 0:
            rsi_vals.append(100.0)
        else:
            rs = g / l
            rsi_vals.append(100.0 - (100.0 / (1.0 + rs)))
    return rsi_vals


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


class ChartPanel(ttk.Frame):
    """Тройной график: Price + RSI + MACD."""

    def __init__(self, parent: tk.Misc):
        super().__init__(parent)
        self.configure(style="Dark.TFrame")

        self.figure = Figure(figsize=(7.0, 4.0), dpi=100)
        self.ax_price = self.figure.add_subplot(3, 1, 1)
        self.ax_rsi = self.figure.add_subplot(3, 1, 2, sharex=self.ax_price)
        self.ax_macd = self.figure.add_subplot(3, 1, 3, sharex=self.ax_price)

        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    # ------------------------------------------------------------------ API
    def plot_series(self, times: Sequence[int], prices: Sequence[float]) -> None:
        """Отрисовать серии.

        times используется только для длины, по оси X — индекс.
        """
        if not prices:
            # очищаем график
            self.ax_price.cla()
            self.ax_rsi.cla()
            self.ax_macd.cla()
            self.canvas.draw_idle()
            return

        xs = list(range(len(prices)))
        ys = [float(p) for p in prices]

        # --- price
        self.ax_price.cla()
        self.ax_price.plot(xs, ys)
        self.ax_price.set_ylabel("Price")

        # --- RSI
        self.ax_rsi.cla()
        rsi_vals = _rsi(ys, period=14)
        self.ax_rsi.plot(xs, rsi_vals)
        self.ax_rsi.axhline(30, linestyle="--")
        self.ax_rsi.axhline(70, linestyle="--")
        self.ax_rsi.set_ylabel("RSI")
        self.ax_rsi.tick_params(labelbottom=False)

        # --- MACD
        self.ax_macd.cla()
        macd_line, signal_line, hist = _macd(ys)
        if macd_line:
            self.ax_macd.plot(xs[: len(macd_line)], macd_line, label="MACD")
        if signal_line:
            self.ax_macd.plot(xs[: len(signal_line)], signal_line, label="Signal")
        if hist:
            self.ax_macd.bar(xs[: len(hist)], hist, alpha=0.3)
        self.ax_macd.set_ylabel("MACD")
        self.ax_macd.set_xlabel("Index")

        # --- title & layout
        try:
            ticks = len(prices)
            self.figure.suptitle(
                f"MontrixBot — LIVE Chart (ticks={ticks})",
                fontsize=10,
            )
        except Exception:
            pass

        self.figure.tight_layout(rect=[0, 0.03, 1, 0.95])
        self.canvas.draw_idle()
