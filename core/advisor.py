# core/advisor.py
# Простенький модуль рекомендаций по позиции на основе RSI+MACD+тренда.

from __future__ import annotations

from typing import Dict, Any, Sequence, Optional
import math


def _safe_float(v: Optional[float]) -> float:
    try:
        if v is None:
            return float("nan")
        return float(v)
    except Exception:
        return float("nan")


def _trend_score(prices: Sequence[float]) -> float:
    """Оценка тренда по последним ценам в диапазоне [-1; 1]."""

    n = len(prices)
    if n < 4:
        return 0.0
    first = float(prices[0])
    last = float(prices[-1])
    rng = max(prices) - min(prices) if n > 1 else 0.0
    if rng <= 0:
        rng = abs(last) if last != 0 else 1.0
    raw = (last - first) / rng
    return max(-1.0, min(1.0, raw))


def compute_recommendation(
    side: str,
    rsi_last: Optional[float],
    macd_last: Optional[float],
    macd_signal_last: Optional[float],
    prices: Sequence[float],
) -> Dict[str, Any]:
    """Вернуть рекомендацию BUY/SELL/HOLD с силой и кратким описанием.

    Это не торговая стратегия, а индикативный блок советов для UI.
    """

    side = (side or "HOLD").upper()
    rsi = _safe_float(rsi_last)
    macd = _safe_float(macd_last)
    macd_sig = _safe_float(macd_signal_last)

    trend = _trend_score(prices)
    if trend > 0.2:
        trend_label = "UP"
    elif trend < -0.2:
        trend_label = "DOWN"
    else:
        trend_label = "FLAT"

    # ------------------------ локальные оценки ------------------------
    bias = 0.0

    # RSI: чем дальше от 50, тем сильнее сигнал BUY/SELL
    if not math.isnan(rsi):
        if rsi < 30:
            rsi_dir = 1.0
        elif rsi > 70:
            rsi_dir = -1.0
        elif rsi < 50:
            rsi_dir = 0.3
        else:
            rsi_dir = -0.3
        rsi_intensity = 1.0 - min(abs(rsi - 50.0) / 50.0, 1.0)
        bias += 0.4 * rsi_dir * (1.0 - rsi_intensity)

    # MACD: разница с сигнальной линией
    if not math.isnan(macd) and not math.isnan(macd_sig):
        delta = macd - macd_sig
        if delta > 0:
            macd_dir = 1.0
        elif delta < 0:
            macd_dir = -1.0
        else:
            macd_dir = 0.0
        macd_intensity = min(abs(delta) * 10.0, 1.0)
        bias += 0.3 * macd_dir * macd_intensity

    # Тренд по ценам
    if trend > 0:
        trend_dir = 1.0
    elif trend < 0:
        trend_dir = -1.0
    else:
        trend_dir = 0.0
    bias += 0.3 * trend_dir * abs(trend)

    # Базовое смещение от исходного сигнала
    base = 0.0
    if side == "BUY":
        base = 0.4
    elif side == "SELL":
        base = -0.4

    score = base + bias
    score = max(-1.0, min(1.0, score))

    if score >= 0.15:
        reco_side = "BUY"
    elif score <= -0.15:
        reco_side = "SELL"
    else:
        reco_side = "HOLD"

    strength = min(1.0, abs(score))

    parts = [f"trend={trend_label}"]

    if not math.isnan(rsi):
        if rsi < 30:
            parts.append("RSI oversold")
        elif rsi > 70:
            parts.append("RSI overbought")
        else:
            parts.append("RSI neutral")

    if not math.isnan(macd) and not math.isnan(macd_sig):
        delta = macd - macd_sig
        if delta > 0:
            parts.append("MACD bullish")
        elif delta < 0:
            parts.append("MACD bearish")
        else:
            parts.append("MACD flat")

    reason = ", ".join(parts)

    return {
        "side": reco_side,
        "strength": strength,
        "trend": trend_label,
        "score": score,
        "reason": reason,
    }
