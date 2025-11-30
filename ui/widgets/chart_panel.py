# ui/widgets/chart_panel.py
# Simple Price + RSI + MACD panel for MontrixBot.
# Does not depend on core.indicators, everything is calculated locally.

from __future__ import annotations

import math
import json
from typing import List, Sequence, Tuple
from pathlib import Path

import tkinter as tk
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
RUNTIME_DIR = ROOT_DIR / "runtime"
SIGNALS_FILE = RUNTIME_DIR / "signals.jsonl"

def _ema(values: Sequence[float], period: int) -> List[float]:
    """Simple EMA implementation for demo charts."""
    values = list(values)
    if not values or period <= 1:
        return [float(v) for v in values]

    alpha = 2.0 / (period + 1.0)
    ema_vals: List[float] = []
    ema_prev = float(values[0])
    ema_vals.append(ema_prev)
    for v in values[1:]:
        ema_prev = alpha * float(v) + (1.0 - alpha) * ema_prev
        ema_vals.append(ema_prev)
    return ema_vals


def _rsi(values: Sequence[float], period: int = 14) -> List[float]:
    """Classic RSI (Wilder) for demo charts."""
    values = list(values)
    n = len(values)
    if n == 0:
        return []
    if n <= period:
        return [50.0] * n

    gains: List[float] = [0.0] * n
    losses: List[float] = [0.0] * n

    for i in range(1, n):
        diff = float(values[i]) - float(values[i - 1])
        if diff >= 0:
            gains[i] = diff
        else:
            losses[i] = -diff

    avg_gain = sum(gains[1 : period + 1]) / period
    avg_loss = sum(losses[1 : period + 1]) / period

    rsi_vals: List[float] = [50.0] * n

    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            rs = float("inf")
        else:
            rs = avg_gain / avg_loss

        rsi_vals[i] = 100.0 - (100.0 / (1.0 + rs))

    # fill the first "period" values with the first computed RSI
    first_val = rsi_vals[period]
    for i in range(period):
        rsi_vals[i] = first_val

    return rsi_vals


def _macd(
    values: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Tuple[List[float], List[float]]:
    """MACD line and signal line."""
    values = list(values)
    if not values:
        return [], []

    ema_fast = _ema(values, fast)
    ema_slow = _ema(values, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = _ema(macd_line, signal)
    return macd_line, signal_line



def _load_strategy_signals(max_points: int = 500) -> List[dict]:
    """Загрузить последние сигналы стратегии из runtime/signals.jsonl."""

    if not SIGNALS_FILE.exists():
        return []
    try:
        with SIGNALS_FILE.open("r", encoding="utf-8") as f:
            lines = f.readlines()[-max_points:]
    except Exception:
        return []
    result: List[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if "index" not in obj or "side" not in obj:
            continue
        result.append(obj)
    return result


class ChartPanel(ttk.Frame):
    """Tkinter frame with embedded Matplotlib figure.

    Methods
    -------
    plot_series(x, prices, symbol=None)
        Draw Price + RSI + MACD stacked chart.
    """

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, **kwargs)

        # Figure with 3 rows: Price, RSI, MACD
        self.figure = Figure(figsize=(6, 4), dpi=100)
        grid = self.figure.add_gridspec(
            3, 1, height_ratios=[2.0, 1.0, 1.0], hspace=0.1
        )

        self.ax_price = self.figure.add_subplot(grid[0, 0])
        self.ax_rsi = self.figure.add_subplot(grid[1, 0], sharex=self.ax_price)
        self.ax_macd = self.figure.add_subplot(grid[2, 0], sharex=self.ax_price)

        # Canvas
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        widget = self.canvas.get_tk_widget()
        widget.pack(fill="both", expand=True)

        self._setup_axes()

    # ------------------------------------------------------------------ #
    # Axes and styling
    # ------------------------------------------------------------------ #
    def _setup_axes(self) -> None:
        self.ax_price.set_ylabel("Price")
        self.ax_rsi.set_ylabel("RSI")
        self.ax_macd.set_ylabel("MACD")

        # RSI fixed range
        self.ax_rsi.set_ylim(0, 100)
        self.ax_rsi.axhline(70, color="red", linestyle="--", linewidth=0.8)
        self.ax_rsi.axhline(30, color="blue", linestyle="--", linewidth=0.8)

        # MACD zero line
        self.ax_macd.axhline(0, color="black", linewidth=0.8)

        # x labels only on MACD
        self.ax_price.tick_params(labelbottom=False)
        self.ax_rsi.tick_params(labelbottom=False)
        self.ax_macd.set_xlabel("Index")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def plot_series(
        self,
        x: Sequence[float],
        prices: Sequence[float],
        symbol: str | None = None,
    ) -> None:
        """Draw / update all three panels.

        Parameters
        ----------
        x : sequence of numbers
            X axis (index, timestamps, etc).
        prices : sequence of floats
            Price series.
        symbol : str, optional
            Used only in title (for information).
        """
        x = list(x)
        prices = [float(p) for p in prices]
        if not x or not prices:
            # nothing to draw
            return

        # Make lengths equal if needed
        n = min(len(x), len(prices))
        x = x[:n]
        prices = prices[:n]

        # Compute indicators
        rsi_vals = _rsi(prices, period=14)
        macd_line, signal_line = _macd(prices, fast=12, slow=26, signal=9)

        # Clear previous content
        self.ax_price.cla()
        self.ax_rsi.cla()
        self.ax_macd.cla()

        # Price
        self.ax_price.plot(x, prices, linewidth=1.0, label="Price")
        self.ax_price.set_ylabel("Price")

        # Expand y limits a bit
        p_min = min(prices)
        p_max = max(prices)
        pad = (p_max - p_min) * 0.05 if p_max > p_min else 1.0
        self.ax_price.set_ylim(p_min - pad, p_max + pad)
        
        # --- Moving Averages (EMA20 / EMA50) ---
        try:
            ema_fast = _ema(prices, period=20)
            ema_slow = _ema(prices, period=50)

            # Рисуем поверх цены пунктиром
            self.ax_price.plot(x, ema_fast, linewidth=0.9, linestyle="--", label="EMA20")
            self.ax_price.plot(x, ema_slow, linewidth=0.9, linestyle="-.", label="EMA50")
        except Exception:
            pass

        # RSI
        self.ax_rsi.plot(x, rsi_vals, linewidth=0.9)
        self.ax_rsi.set_ylabel("RSI")
        self.ax_rsi.set_ylim(0, 100)
        self.ax_rsi.axhline(70, color="red", linestyle="--", linewidth=0.8)
        self.ax_rsi.axhline(30, color="blue", linestyle="--", linewidth=0.8)

        # MACD
        self.ax_macd.plot(x, macd_line, linewidth=0.9, label="MACD")
        self.ax_macd.plot(x, signal_line, linewidth=0.9, linestyle="--", label="Signal")
        self.ax_macd.set_ylabel("MACD")
        self.ax_macd.axhline(0, color="black", linewidth=0.8)
        self.ax_macd.legend(loc="upper left", fontsize="x-small")

        # Стрелки BUY/SELL по стратегии
        signals = _load_strategy_signals(max_points=len(prices))
        buy_x: List[float] = []
        buy_y: List[float] = []
        buy_s: List[float] = []
        sell_x: List[float] = []
        sell_y: List[float] = []
        sell_s: List[float] = []
        if signals:
            for obj in signals: 
                try:
                    idx = int(obj.get("index", -1))
                except Exception:
                    continue
                if idx < 0 or idx >= len(prices):
                    continue

                # если указан symbol для графика — фильтруем сигналы только по нему
                if symbol:
                    sig_sym = str(obj.get("symbol", "")).upper()
                    if sig_sym and sig_sym != str(symbol).upper():
                        continue

                side = str(obj.get("side", "")).upper()
                xi = x[idx]
                pi = prices[idx]

                # масштабируем размер маркера по силе сигнала (0..1)
                strength = 0.0
                try:
                    strength = float(obj.get("signal_strength", 0.0))
                except Exception:
                    strength = 0.0
                # базовый размер 30, при сильном сигнале увеличиваем
                size = 30.0 + max(0.0, min(1.0, strength)) * 40.0

                if side == "BUY":
                    buy_x.append(xi)
                    buy_y.append(pi)
                    buy_s.append(size)
                elif side == "SELL":
                    sell_x.append(xi)
                    sell_y.append(pi)
                    sell_s.append(size)
                if buy_x:
                    self.ax_price.scatter(
                        buy_x, buy_y,
                        marker="^",
                        color="green",
                        s=buy_s or 30,
                        label="BUY"
                    )

                if sell_x:
                    self.ax_price.scatter(
                        sell_x, sell_y,
                        marker="v",
                        color="red",
                        s=sell_s or 30,
                        label="SELL"
                    )

        # компактная легенда по цене/EMA/BUY/SELL
        try:
            handles, labels = self.ax_price.get_legend_handles_labels()
            if labels:
                seen = set()
                uniq_h = []
                uniq_l = []
                for h, lab in zip(handles, labels):
                    if lab in seen:
                        continue
                    seen.add(lab)
                    uniq_h.append(h)
                    uniq_l.append(lab)
                self.ax_price.legend(uniq_h, uniq_l, loc="upper left", fontsize=8)
        except Exception:
            pass

        # X labels only on MACD
        self.ax_price.tick_params(labelbottom=False)
        self.ax_rsi.tick_params(labelbottom=False)
        self.ax_macd.set_xlabel("Index")

        # Title
        ticks = len(prices)
        if symbol:
            title = f"MontrixBot — LIVE Chart (symbol={symbol}, ticks={ticks})"
        else:
            title = f"MontrixBot — LIVE Chart (ticks={ticks})"
        self.figure.suptitle(title, fontsize=10)

        # Layout and redraw
        self.figure.tight_layout(rect=[0, 0.03, 1, 0.95])
        self.canvas.draw_idle()
