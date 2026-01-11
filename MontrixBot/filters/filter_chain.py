"""
filters.filter_chain
--------------------

Цепочка фильтров (FilterChain) для последовательной проверки контекста.

Идея простая:

    chain = FilterChain.from_default_config()
    if not chain.apply_all(context):
        # сигнал/символ отбрасывается

На шаге 1.1.A реальных фильтров ещё нет, цепочка пустая, поэтому
apply_all() всегда возвращает True и поведение бота НЕ МЕНЯЕТСЯ.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

from .base_filter import BaseFilter, FilterContext

# Пытаемся подтянуть дефолтную конфигурацию фильтров.
# Если модуль по какой-то причине недоступен, просто работаем без неё.
try:
    from config.filters_config import DEFAULT_FILTERS  # type: ignore
except Exception:  # noqa: BLE001
    DEFAULT_FILTERS: Dict[str, Any] = {}

# Опциональный импорт конкретных фильтров.
# На шаге 1.1.B нам нужен только EMAFilter.
try:
    from .ema_filter import EMAFilter  # type: ignore
except Exception:  # noqa: BLE001
    EMAFilter = None  # type: ignore

# VolumeFilter будет использоваться на шаге 1.1.C
try:
    from .volume_filter import VolumeFilter  # type: ignore
except Exception:  # noqa: BLE001
    VolumeFilter = None  # type: ignore

# NewsFilter используется на шаге 1.1.D
try:
    from .news_filter import NewsFilter  # type: ignore
except Exception:  # noqa: BLE001
    NewsFilter = None  # type: ignore

@dataclass
class FilterChain:
    """
    Коллекция фильтров, применяемых последовательно.

    Если хотя бы один включённый фильтр возвращает False,
    вся цепочка считается "не пройденной".
    """

    filters: List[BaseFilter] = field(default_factory=list)

    def add(self, flt: BaseFilter) -> None:
        """Добавить фильтр в цепочку."""
        self.filters.append(flt)

    def apply_all(self, context: FilterContext) -> bool:
        """
        Применить все включённые фильтры к контексту.

        ВАЖНО: ошибки внутри отдельного фильтра не должны ломать всю цепочку,
        поэтому любые исключения логически игнорируются (будем их логировать
        позже, на следующих шагах).
        """
        if not self.filters:
            # На шаге 1.1.A фильтров нет -> ничего не фильтруем.
            return True

        for flt in self.filters:
            if not getattr(flt, "enabled", True):
                # Выключенный фильтр пропускаем
                continue
            try:
                if not flt.apply(context):
                    return False
            except Exception:
                # В случае проблем с конкретным фильтром не роняем пайплайн.
                # Здесь позже добавим логирование.
                continue

        return True

    @classmethod
    def from_config(cls, cfg: Optional[Dict[str, Any]] = None) -> "FilterChain":
        """
        Сконструировать цепочку фильтров из конфигурации.

        Ожидается, что cfg совместим с config.filters_config.DEFAULT_FILTERS:
            {
                "ema": {...},
                "volume": {...},
                "news": {...},
                ...
            }
        """
        chain = cls()

        # Если конфиг не передали, используем дефолтный
        if cfg is None:
            cfg = DEFAULT_FILTERS

        if not isinstance(cfg, dict):
            return chain

        # --- EMA-фильтр ---
        try:
            if EMAFilter is not None:
                ema_cfg = cfg.get("ema") or {}
                enabled = bool(ema_cfg.get("enabled", False))
                if enabled:
                    flt = EMAFilter(**ema_cfg)
                    chain.add(flt)
        except Exception:
            # Любые проблемы с конкретным фильтром не должны ломать пайплайн
            pass

        # --- Volume-фильтр ---
        try:
            if VolumeFilter is not None:
                vol_cfg = cfg.get("volume") or {}
                enabled = bool(vol_cfg.get("enabled", False))
                if enabled:
                    flt = VolumeFilter(**vol_cfg)
                    chain.add(flt)
        except Exception:
            # Любые проблемы с конкретным фильтром не должны ломать пайплайн
            pass

        # --- News-фильтр ---
        try:
            if NewsFilter is not None:
                news_cfg = cfg.get("news") or {}
                enabled = bool(news_cfg.get("enabled", False))
                if enabled:
                    flt = NewsFilter(**news_cfg)
                    chain.add(flt)
        except Exception:
            # Любые проблемы с конкретным фильтром не должны ломать пайплайн
            pass

        return chain
