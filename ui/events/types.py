# ui/events/types.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class Event:
    """Базовый тип события для Unified Event System (UI).

    Минимальный контракт:
    - type: строковый тип события (snapshot/signal/...);
    - ts: timestamp в секундах (time.time());
    - source: человекочитаемый источник события (TickUpdater, UI, core и т.д.);
    - payload: произвольный словарь с данными события.
    """  # noqa: E501

    type: str
    ts: float
    source: str
    payload: Dict[str, Any]


# Базовые типы событий, которые мы используем на STEP1.3.4
EVT_SNAPSHOT = "snapshot"
EVT_SIGNAL = "signal"
EVT_EQUITY = "equity"
EVT_HEALTH = "health"
EVT_LOG = "log"
