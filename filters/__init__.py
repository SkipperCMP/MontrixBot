"""
filters
-------

Инфраструктура фильтров стратегий для MontrixBot 1.1+.

На шаге 1.1.A здесь только базовые классы и цепочка фильтров
без изменения поведения бота. Реальные фильтры (EMA/объём/новости)
будут добавлены на следующих шагах (1.1.B+).
"""

from __future__ import annotations

from .base_filter import BaseFilter, FilterContext
from .filter_chain import FilterChain

__all__ = ("BaseFilter", "FilterContext", "FilterChain")
