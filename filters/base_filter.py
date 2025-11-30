"""
filters.base_filter
-------------------

Базовый интерфейс фильтра сигналов/символов.

Фильтр получает "контекст" (словари с данными по символу,
индикаторам, объёмам, новостям и т.д.) и возвращает:

    True  — если контекст ПРОХОДИТ фильтр
    False — если контекст ОТБРАСЫВАЕТСЯ фильтром

На шаге 1.1.A это только инфраструктура, конкретные фильтры
(EMA/объём/новости) будут реализованы позже.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol


# Унифицированный тип контекста фильтра.
FilterContext = Mapping[str, Any]


class SupportsFilter(Protocol):
    """Простейший протокол для фильтра, если понадобится duck-typing."""

    name: str
    enabled: bool

    def apply(self, context: FilterContext) -> bool:  # pragma: no cover - интерфейс
        ...


@dataclass
class BaseFilter:
    """
    Базовый класс фильтра.

    Наследники должны переопределить метод apply().
    Атрибут enabled используется FilterChain'ом — если фильтр выключен,
    он не применяется.
    """

    name: str
    enabled: bool = True

    def apply(self, context: FilterContext) -> bool:
        """
        Применить фильтр к контексту.

        Базовая реализация НИЧЕГО НЕ ФИЛЬТРУЕТ и всегда возвращает True.
        Наследники должны реализовать собственную логику.
        """
        return True
