"""
core.signals
------------
Простейшая логика сигналов на основе RSI + MACD для MontrixBot 1.1-SIGNALS.

Функция simple_rsi_macd возвращает словарь:
    {
        "side":   "BUY" | "SELL" | "HOLD",
        "reason": str,
        "rsi":     float,   # последнее валидное значение RSI
        "macd":    float,   # последнее валидное значение MACD
        "macd_sig":float,   # последнее валидное значение сигнальной линии MACD
    }
"""

from __future__ import annotations
from typing import Iterable, Dict, Any, Optional
from dataclasses import dataclass
import math

from filters.filter_chain import FilterChain
from config.filters_config import DEFAULT_FILTERS  # type: ignore

# Глобальная цепочка фильтров для сигналов (инициализируется из конфига 1.1)
try:
    _DEFAULT_FILTER_CHAIN: Optional[FilterChain]
    _DEFAULT_FILTER_CHAIN = FilterChain.from_config(DEFAULT_FILTERS)
except Exception:
    _DEFAULT_FILTER_CHAIN = None


def _apply_filters_for_signal(
    symbol: Optional[str],
    rsi_val: float,
    macd_val: float,
    macd_sig_val: float,
    ema_fast_val: Optional[float] = None,
    ema_slow_val: Optional[float] = None,
    price_last: Optional[float] = None,
) -> bool:
    """
    Применяем цепочку фильтров 1.1 (EMA / volume / news) к сигналу.

    Сейчас контекст содержит только базовые поля + заглушки для объёма/новостей,
    поэтому при enabled=False поведение полностью прежнее.
    """
    chain = _DEFAULT_FILTER_CHAIN
    if chain is None:
        return True

    context: Dict[str, Any] = {
        "symbol": (symbol or "").upper(),
        "rsi": float(rsi_val),
        "macd": float(macd_val),
        "macd_sig": float(macd_sig_val),
        # реальные значения EMA-фильтра (если есть)
        "ema_fast": float(ema_fast_val) if ema_fast_val is not None else None,
        "ema_slow": float(ema_slow_val) if ema_slow_val is not None else None,
        "price_last": float(price_last) if price_last is not None else None,
        # заглушки для фильтра по объёму
        "quote_volume_24h": None,
        "best_bid": None,
        "best_ask": None,
        "tick_volume": None,
        # заглушки для фильтра новостей
        "news_sentiment": None,
        "news_score": None,
    }

    try:
        return chain.apply_all(context)
    except Exception:
        # любые проблемы с фильтрами не должны ломать сигналы
        return True


def _last_valid(values: Iterable[float]) -> float:
    last = float("nan")
    for v in values:
        try:
            f = float(v)
        except Exception:
            continue
        last = f
    return last


def simple_rsi_macd(
    rsi_series: Iterable[float],
    macd_series: Iterable[float],
    macd_signal_series: Iterable[float],
    rsi_overbought: float = 70.0,
    rsi_oversold: float = 30.0,
) -> Dict[str, Any]:
    """
    Мини-комбайн сигналов.

    Логика нарочито простая и "обучаемая" в будущем:
      * RSI < rsi_oversold  -> базовый сигнал BUY
      * RSI > rsi_overbought -> базовый сигнал SELL
      * иначе базовый сигнал HOLD

    MACD уточняет сторону:
      * если базовый BUY и MACD > signal  -> подтверждение вверх
      * если базовый SELL и MACD < signal -> подтверждение вниз
      * если базовый HOLD, но MACD значительно выше/ниже сигнальной,
        можем подсказать мягкий BUY/SELL.

    Возвращает словарь с итоговым решением.
    """
    rsi_val = _last_valid(list(rsi_series))
    macd_val = _last_valid(list(macd_series))
    sig_val = _last_valid(list(macd_signal_series))

    side = "HOLD"
    reason = "neutral zone"

    # --- базовый сигнал по RSI ---
    if not math.isnan(rsi_val):
        if rsi_val < rsi_oversold:
            side = "BUY"
            reason = "RSI oversold"
        elif rsi_val > rsi_overbought:
            side = "SELL"
            reason = "RSI overbought"

    # --- уточнение по MACD ---
    if not math.isnan(macd_val) and not math.isnan(sig_val):
        delta = macd_val - sig_val

        if side == "BUY":
            if delta > 0:
                reason += ", MACD confirms up"
            else:
                reason += ", MACD weak / no confirm"
        elif side == "SELL":
            if delta < 0:
                reason += ", MACD confirms down"
            else:
                reason += ", MACD weak / no confirm"
        else:  # HOLD
            # Лёгкий уклон, если MACD сильно разошёлся с сигнальной
            if delta > 0:
                side = "BUY"
                reason = "MACD bullish, RSI neutral"
            elif delta < 0:
                side = "SELL"
                reason = "MACD bearish, RSI neutral"

    strength = 0.0
    try:
        if side in ("BUY", "SELL"):
            span = max(1e-6, float(rsi_overbought) - float(rsi_oversold))
            if not math.isnan(rsi_val):
                if side == "BUY":
                    rsi_score = (float(rsi_overbought) - float(rsi_val)) / span
                else:
                    rsi_score = (float(rsi_val) - float(rsi_oversold)) / span
                rsi_score = max(0.0, min(1.0, rsi_score))
            else:
                rsi_score = 0.0

            macd_score = 0.0
            if not math.isnan(macd_val) and not math.isnan(sig_val):
                delta = macd_val - sig_val
                if (side == "BUY" and delta > 0) or (side == "SELL" and delta < 0):
                    macd_score = min(1.0, abs(delta) * 5.0)

            strength = max(0.0, min(1.0, 0.6 * rsi_score + 0.4 * macd_score))
    except Exception:
        strength = 0.0

    return {
        "side": side,
        "reason": reason,
        "rsi": rsi_val,
        "macd": macd_val,
        "macd_sig": sig_val,
        "strength": strength,
    }

@dataclass
class SimpleSignal:
    """Простой контейнер для результата simple_rsi_macd_signal.

    Совместим с UI (атрибуты side/reason/rsi/macd/macd_signal и as_dict()).
    """

    side: str
    reason: str
    rsi: float
    macd: float
    macd_signal: float
    strength: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "side": self.side,
            "reason": self.reason,
            "rsi": self.rsi,
            "macd": self.macd,
            "macd_signal": self.macd_signal,
            "strength": self.strength,
        }


def simple_rsi_macd_signal(
    rsi_last: Optional[float],
    macd_last: Optional[float],
    macd_signal_last: Optional[float],
    rsi_overbought: float = 70.0,
    rsi_oversold: float = 30.0,
    symbol: Optional[str] = None,
    ema_fast_last: Optional[float] = None,
    ema_slow_last: Optional[float] = None,
    price_last: Optional[float] = None,
) -> Optional[SimpleSignal]:
    """Обёртка над simple_rsi_macd для использования из UI.

    Принимает последние значения RSI/MACD и возвращает SimpleSignal
    или None, если сигнал вычислить нельзя.
    """

    if rsi_last is None or (isinstance(rsi_last, float) and math.isnan(rsi_last)):
        return None

    def _norm(v: Optional[float]) -> float:
        if v is None:
            return 0.0
        if isinstance(v, float) and math.isnan(v):
            return 0.0
        try:
            return float(v)
        except Exception:
            return 0.0

    macd_val = _norm(macd_last)
    macd_sig_val = _norm(macd_signal_last)

    data = simple_rsi_macd(
        rsi_series=[rsi_last],
        macd_series=[macd_val],
        macd_signal_series=[macd_sig_val],
        rsi_overbought=rsi_overbought,
        rsi_oversold=rsi_oversold,
    )

    # --- фильтры 1.1: EMA / volume / news ---
    try:
        ok = _apply_filters_for_signal(
            symbol,
            rsi_val,
            macd_val,
            macd_sig_val,
            ema_fast_last,
            ema_slow_last,
            price_last,
        )
        if not ok:
            # фильтры не пропускают сигнал — принудительно HOLD
            data = dict(data)
            data_side = str(data.get("side", "HOLD"))
            base_reason = str(data.get("reason") or "")
            tag = "filtered by EMA/volume/news"
            if base_reason:
                data["reason"] = f"{base_reason}; {tag}"
            else:
                data["reason"] = tag
            data["side"] = "HOLD"
    except Exception:
        # Любые проблемы с фильтрами не должны ломать сигналы.
        # В таком случае просто используем исходный data.
        pass

    return SimpleSignal(
        side=str(data.get("side", "HOLD")),
        reason=str(data.get("reason", "")),
        rsi=float(data.get("rsi", float("nan"))),
        macd=float(data.get("macd", float("nan"))),
        macd_signal=float(data.get("macd_sig", float("nan"))),
        strength=float(data.get("strength", 0.0)),
    )
