"""
core.news_provider_stub
-----------------------

Stub-провайдер новостей/сентимента для MontrixBot 1.1.D.

На этом шаге он не подключён к реальным источникам,
а просто возвращает нейтральный сентимент для любого символа.

Позже можно будет заменить/расширить:
    * подключить реальные API новостей,
    * кэшировать результаты,
    * использовать разные таймфреймы и источники.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class NewsSentiment:
    symbol: str
    sentiment: float  # -1.0 .. +1.0
    score: float      # 0.0 .. 1.0
    source: str = "stub"


def get_symbol_sentiment(symbol: str) -> NewsSentiment:
    """
    Вернуть нейтральную оценку сентимента по символу.

    Сейчас это просто заглушка:
        sentiment = 0.0 (нейтральный)
        score     = 0.0 (нет уверенности)
    """
    return NewsSentiment(symbol=symbol.upper(), sentiment=0.0, score=0.0, source="stub")


def as_context_dict(sent: NewsSentiment) -> Dict[str, float]:
    """
    Преобразовать NewsSentiment в словарь для контекста фильтров.
    """
    return {
        "news_sentiment": float(sent.sentiment),
        "news_score": float(sent.score),
    }
