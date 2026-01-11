"""
config.filters_config
---------------------

Дефолтная конфигурация фильтров MontrixBot 1.1.

На шаге 1.1.A это только значения по умолчанию, которые:
    - описывают, какие фильтры вообще существуют;
    - все фильтры выключены (enabled = False);
    - содержат задел под параметры, которые понадобятся позже.

Реальные фильтры (EMA/объём/новости) появятся на шагах 1.1.B+,
и будут читать параметры из этой структуры.
"""

from __future__ import annotations

from typing import Any, Dict


# Структура: имя_фильтра -> словарь с параметрами.
DEFAULT_FILTERS: Dict[str, Dict[str, Any]] = {
    "ema": {
        "enabled": False,
        # Параметры по умолчанию (будут использоваться в 1.1.B):
        "short_period": 20,
        "long_period": 50,
        "min_trend_strength": 0.0,
    },
    "volume": {
        "enabled": False,
        # Параметры по умолчанию (1.1.C):
        "min_24h_quote_volume": 100_000.0,
        "max_spread": 0.01,  # 1 %
        "min_tick_volume": 0.0,
    },
    "news": {
        "enabled": False,
        # Параметры по умолчанию (1.1.D):
        "allowed_sentiment": "neutral_or_positive",
        "min_score": 0.0,
        "treat_missing_as_neutral": True,
    },
}
