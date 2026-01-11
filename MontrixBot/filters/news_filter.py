"""
filters.news_filter
--------------------

Фильтр новостей/сентимента для MontrixBot 1.1.D.

Сейчас работает на stub-данных: ожидает в контексте поля
    * news_sentiment  (float, -1.0..+1.0; отрицательные = плохие новости)
    * news_score      (float, 0.0..1.0; насколько уверены в оценке)

На этом шаге:
    * конфигурация берётся из config.filters_config["news"]
    * фильтр ВЫКЛЮЧЕН по умолчанию (enabled=False)
    * если данных по новостям нет, и treat_missing_as_neutral=True,
      то контекст пропускается (fail-open).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import math

from .base_filter import BaseFilter, FilterContext


@dataclass
class NewsFilter(BaseFilter):
    """
    Фильтр по новостям/сентименту.

    Параметры
    ---------
    enabled : bool
        Включён/выключен фильтр.
    allowed_sentiment : str
        Режим допуска. На данном шаге поддерживаем строки:
            * "any"                   — не фильтруем по сентименту
            * "neutral_or_positive"   — не допускаем сильно негативный сентимент
    min_score : float
        Минимальная "уверенность" в оценке сентимента (0.0..1.0).
    treat_missing_as_neutral : bool
        Если True и данных по новостям нет — считаем, что всё ок и пропускаем.
    """

    name: str = "news"
    allowed_sentiment: str = "neutral_or_positive"
    min_score: float = 0.0
    treat_missing_as_neutral: bool = True

    def __init__(
        self,
        enabled: bool = True,
        allowed_sentiment: str = "neutral_or_positive",
        min_score: float = 0.0,
        treat_missing_as_neutral: bool = True,
        name: str = "news",
        **_: Any,
    ) -> None:
        super().__init__(name=name, enabled=enabled)
        self.allowed_sentiment = str(allowed_sentiment or "neutral_or_positive")
        self.min_score = float(min_score)
        self.treat_missing_as_neutral = bool(treat_missing_as_neutral)

    def apply(self, context: FilterContext) -> bool:
        if not self.enabled:
            return True

        # Достаём данные из контекста
        sentiment_raw = context.get("news_sentiment")
        score_raw = context.get("news_score")

        if sentiment_raw is None or score_raw is None:
            # Нет данных по новостям
            return True if self.treat_missing_as_neutral else False

        try:
            sentiment = float(sentiment_raw)
            score = float(score_raw)
        except Exception:
            # Некорректные значения — просто пропускаем
            return True

        if any(math.isnan(v) or math.isinf(v) for v in (sentiment, score)):
            return True

        # Проверка минимальной уверенности
        if score < self.min_score:
            # Если уверенность ниже порога — по сути "не знаем" => neutral
            return True

        mode = self.allowed_sentiment.lower().strip()

        if mode == "any":
            return True

        if mode == "neutral_or_positive":
            # Простейшая логика: сильно негативный сентимент отбрасываем.
            # Можно позже сделать порог/градации.
            if sentiment < 0.0:
                return False
            return True

        # Неизвестный режим — не режем
        return True
