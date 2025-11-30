"""
filters.volume_filter
---------------------

Фильтр ликвидности и объёма.

Проверяет:
    * 24h quote volume (минимальная ликвидность по символу),
    * спред между лучшими bid/ask,
    * при необходимости — объём тиков.

Все параметры читаются из config/filters_config.DEFAULT_FILTERS["volume"].

ВАЖНО:
    На данном шаге фильтр по умолчанию ВЫКЛЮЧЕН (enabled=False в конфиге),
    поэтому поведение бота не меняется, даже если VolumeFilter подключён
    в FilterChain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import math

from .base_filter import BaseFilter, FilterContext


@dataclass
class VolumeFilter(BaseFilter):
    """
    Фильтр по объёму/ликвидности.

    Параметры
    ---------
    enabled : bool
        Включён/выключен фильтр.
    min_24h_quote_volume : float
        Минимальный 24h quote volume (например, в USDT).
    max_spread : float
        Максимально допустимый относительный спред (0.01 = 1%).
    min_tick_volume : float
        Минимальный объём по тик-сводке за недавний период (может быть 0.0).
    """

    name: str = "volume"
    min_24h_quote_volume: float = 0.0
    max_spread: float = 1.0
    min_tick_volume: float = 0.0

    def __init__(
        self,
        enabled: bool = True,
        min_24h_quote_volume: float = 0.0,
        max_spread: float = 1.0,
        min_tick_volume: float = 0.0,
        name: str = "volume",
        **_: Any,
    ) -> None:
        super().__init__(name=name, enabled=enabled)
        self.min_24h_quote_volume = float(min_24h_quote_volume)
        self.max_spread = float(max_spread)
        self.min_tick_volume = float(min_tick_volume)

    def apply(self, context: FilterContext) -> bool:
        """
        Применить фильтр к контексту.

        Ожидаемые поля контекста (в дальнейшем будут заполняться advisor'ом):

            quote_volume_24h : float | None
            best_bid         : float | None
            best_ask         : float | None
            tick_volume      : float | None

        Если данных нет или они некорректны, фильтр НИКОГО НЕ РЕЖЕТ и
        возвращает True (fail-open).
        """
        if not self.enabled:
            return True

        # --- 1. 24h quote volume ---
        vol24 = context.get("quote_volume_24h")
        try:
            v24 = float(vol24)
            if math.isnan(v24) or math.isinf(v24):
                return True
            if v24 < self.min_24h_quote_volume:
                return False
        except Exception:
            # Нет валидных данных по объёму — не режем
            return True

        # --- 2. Относительный спред (ask-bid)/mid ---
        bid = context.get("best_bid")
        ask = context.get("best_ask")

        try:
            bid_f = float(bid)
            ask_f = float(ask)
        except Exception:
            # Нет стакана — не режем
            return True

        if bid_f <= 0.0 or ask_f <= 0.0:
            return True

        mid = 0.5 * (bid_f + ask_f)
        if mid <= 0.0:
            return True

        spread = abs(ask_f - bid_f) / mid
        if spread > self.max_spread:
            return False

        # --- 3. Tick volume (опционально) ---
        tick_vol = context.get("tick_volume")
        if tick_vol is not None:
            try:
                tv = float(tick_vol)
                if not math.isnan(tv) and not math.isinf(tv):
                    if tv < self.min_tick_volume:
                        return False
            except Exception:
                # Некорректное значение — просто игнорируем
                pass

        return True
