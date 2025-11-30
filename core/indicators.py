"""Minimal indicator helpers for MontrixBot 1.1-SIGNALS.

This module is intentionally self-contained and liberal with its API so it
can be called from different parts of the project without raising
TypeError on unexpected keyword arguments.

Exposed functions
-----------------
rsi(prices, period=14, **kwargs) -> list[float]
    Wilder-style RSI. Accepts keyword argument ``period`` and ignores
    any extra kwargs.

macd(prices, fast=12, slow=26, signal=9, **kwargs)
    MACD line and signal line. Also accepts alternative keyword names
    ``period_fast``, ``period_slow`` and ``period_signal``.
"""

from __future__ import annotations

from typing import Iterable, List, Tuple
import math


__all__ = ["rsi", "macd"]


def _to_float_list(values: Iterable[float]) -> List[float]:
    """Convert any iterable of numbers to a list of float."""
    return [float(v) for v in values]


# ---------------------------------------------------------------------------
# RSI (Wilder)
# ---------------------------------------------------------------------------
def rsi(values: Iterable[float], period: int = 14, **kwargs) -> List[float]:
    """Compute Wilder RSI series.

    Parameters
    ----------
    values:
        Iterable with price values.
    period:
        Lookback period for RSI. May also be passed via ``period`` in
        ``kwargs``; any other extra kwargs are silently ignored.

    Returns
    -------
    List[float]
        RSI values with ``math.nan`` where the indicator is not yet
        defined.
    """
    # allow passing `period` either positionally or via kwargs
    if "period" in kwargs and kwargs["period"] is not None:
        period = int(kwargs["period"])

    vals = _to_float_list(values)
    n = int(period)
    length = len(vals)

    if n <= 0:
        raise ValueError("period must be > 0")

    if length == 0:
        return []

    # pre-fill with NaN
    out: List[float] = [math.nan] * length

    # Need at least n+1 prices to have n deltas
    if length <= n:
        return out

    # initial average gain/loss over first `n` deltas
    gains: List[float] = []
    losses: List[float] = []
    for i in range(1, n + 1):
        delta = vals[i] - vals[i - 1]
        if delta >= 0:
            gains.append(delta)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(-delta)

    avg_gain = sum(gains) / n
    avg_loss = sum(losses) / n

    if avg_loss == 0:
        out[n] = 100.0
    else:
        rs = avg_gain / avg_loss
        out[n] = 100.0 - 100.0 / (1.0 + rs)

    # Wilder smoothing for the rest
    for i in range(n + 1, length):
        delta = vals[i] - vals[i - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)

        avg_gain = (avg_gain * (n - 1) + gain) / n
        avg_loss = (avg_loss * (n - 1) + loss) / n

        if avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - 100.0 / (1.0 + rs)

    return out


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------
def _ema(values: List[float], period: int) -> List[float]:
    """Simple EMA implementation returning a list of floats.

    The first ``period-1`` items are ``math.nan``; the value at index
    ``period-1`` is seeded with a simple moving average over the first
    ``period`` prices.
    """
    n = int(period)
    length = len(values)
    if n <= 0:
        raise ValueError("period must be > 0")

    if length == 0:
        return []

    out: List[float] = [math.nan] * length
    if length < n:
        return out

    # seed with SMA
    sma = sum(values[:n]) / n
    out[n - 1] = sma
    prev = sma
    alpha = 2.0 / (n + 1.0)

    for i in range(n, length):
        price = values[i]
        prev = alpha * price + (1.0 - alpha) * prev
        out[i] = prev

    return out

def ema(values: Iterable[float], period: int = 20, **kwargs) -> List[float]:
    """Compute EMA series for given values.

    Parameters
    ----------
    values : iterable of float
        Цена/значения индикатора.
    period : int
        Период EMA. Можно также передать через kwargs["period"].
    kwargs :
        Игнорируются, добавлены для совместимости сигнатур.

    Returns
    -------
    list[float]
        Список значений EMA той же длины, что и values, с NaN в начале там,
        где EMA ещё не определена.
    """
    try:
        # допускаем передачу period через kwargs["period"]
        if isinstance(kwargs, dict) and "period" in kwargs:
            n = int(kwargs.get("period") or period)
        else:
            n = int(period)
    except Exception:
        n = int(period or 1)

    if n <= 0:
        n = 1

    vals = _to_float_list(values)
    return _ema(vals, n)

def macd(
    values: Iterable[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    **kwargs,
) -> Tuple[List[float], List[float]]:
    """Compute MACD and signal lines.

    Accepts the usual ``fast``, ``slow`` and ``signal`` keyword arguments
    as well as aliases ``period_fast``, ``period_slow`` and
    ``period_signal`` via ``kwargs``. Any additional kwargs are ignored.
    """
    # allow alternative keyword names
    fast = int(kwargs.get("period_fast", fast))
    slow = int(kwargs.get("period_slow", slow))
    signal = int(kwargs.get("period_signal", signal))

    vals = _to_float_list(values)

    ema_fast = _ema(vals, fast)
    ema_slow = _ema(vals, slow)

    length = len(vals)
    macd_line: List[float] = [math.nan] * length

    for i in range(length):
        f = ema_fast[i]
        s = ema_slow[i]
        if math.isnan(f) or math.isnan(s):
            macd_line[i] = math.nan
        else:
            macd_line[i] = f - s

    signal_line = _ema(macd_line, signal)

    return macd_line, signal_line
