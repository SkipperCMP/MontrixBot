"""
filters.ema_filter
------------------

EMA-фильтр для MontrixBot 1.1.

На этом шаге фильтр умеет:
    * читать последние значения короткой и длинной EMA
    * оценивать "силу тренда" по разнице между ними
    * отдавать True/False (проходит / не проходит фильтр)

Сам фильтр включается/выключается через config.filters_config.DEFAULT_FILTERS["ema"]["enabled"].
По умолчанию enabled=False, поэтому поведение бота не меняется.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import math

from .base_filter import BaseFilter, FilterContext


@dataclass
class EMAFilter(BaseFilter):
    """
    Фильтр по EMA.

    Параметры
    ---------
    enabled : bool
        Включён/выключен фильтр.
    short_period : int
        Период короткой EMA (ставим тот же, что и в конфиге, например 20).
    long_period : int
        Период длинной EMA (например 50).
    min_trend_strength : float
        Минимальная "силa тренда". Интерпретация:
            * если price известен — относительная разница:
                  |ema_short - ema_long| / price >= min_trend_strength
            * иначе — абсолютная разница:
                  |ema_short - ema_long| >= min_trend_strength
        При значении 0.0 фильтр всегда пропускает контекст.
    """

    short_period: int = 20
    long_period: int = 50
    min_trend_strength: float = 0.0

    def __init__(
        self,
        enabled: bool = True,
        short_period: int = 20,
        long_period: int = 50,
        min_trend_strength: float = 0.0,
        name: str = "ema",
        **_: Any,
    ) -> None:
        super().__init__(name=name, enabled=enabled)
        self.short_period = int(short_period)
        self.long_period = int(long_period)
        self.min_trend_strength = float(min_trend_strength)

    def apply(self, context: FilterContext) -> bool:
        """
        Применить EMA-фильтр к контексту.

        Ожидаемые поля контекста:
            ema_short : float | None
            ema_long  : float | None
            price     : float | None (или price_close)

        Если нужных данных нет или они некорректны — фильтр НИКОГО НЕ РЕЖЕТ
        и возвращает True.
        """
        # если фильтр выключен, цепочка всё равно может его вызвать — просто пропускаем
        if not self.enabled:
            return True

        ema_short = context.get("ema_short")
        ema_long = context.get("ema_long")
        price = context.get("price") or context.get("price_close")

        try:
            ema_s = float(ema_short)
            ema_l = float(ema_long)
        except Exception:
            # нет валидных EMA — не режем
            return True

        if any(math.isnan(v) or math.isinf(v) for v in (ema_s, ema_l)):
            return True

        price_f = None
        if price is not None:
            try:
                price_f = float(price)
            except Exception:
                price_f = None

        strength = abs(ema_s - ema_l)
        threshold = float(self.min_trend_strength)

        # Если порог нулевой или отрицательный, фильтр принято считать "прозрачным"
        if threshold <= 0.0:
            return True

        if price_f is not None and price_f > 0.0:
            rel_strength = strength / price_f
            return rel_strength >= threshold

        # fallback: абсолютная разница
        return strength >= threshold
