# ui/events/bus.py
from __future__ import annotations

from collections import defaultdict
from typing import Callable, DefaultDict, List

from ui.events.types import Event


Callback = Callable[[Event], None]

# UI Unified EventBus
# Единственный допустимый EventBus для UI слоя (STEP1.3.4)
UI_EVENT_BUS = True



class EventBus:
    """Простой in-process EventBus для UI.

    STEP1.3.4 (pre1):
    - никаких потоков и очередей;
    - синхронная доставка событий подписчикам;
    - ошибки подписчиков не ломают общую работу.
    """  # noqa: E501

    def __init__(self) -> None:
        self._subscribers: DefaultDict[str, List[Callback]] = defaultdict(list)

    # -------------------------------------------------------------- subscribe --

    def subscribe(self, event_type: str, callback: Callback) -> None:
        """Подписаться на события указанного типа.

        Повторные подписки одного и того же callback игнорируются.
        """
        if callback in self._subscribers[event_type]:
            return
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callback) -> None:
        """Отписаться от событий указанного типа (если был подписан)."""
        callbacks = self._subscribers.get(event_type)
        if not callbacks:
            return
        try:
            callbacks.remove(callback)
        except ValueError:
            pass

    # ---------------------------------------------------------------- publish --

    def publish(self, event: Event) -> None:
        """Отправить событие всем подписчикам его типа."""
        callbacks = list(self._subscribers.get(event.type, ()))
        for cb in callbacks:
            try:
                cb(event)
            except Exception:
                # ошибки в подписчиках не должны ломать основную работу
                continue

    def stats(self) -> dict:
        """Диагностика: количество подписчиков по типам событий."""
        try:
            return {k: len(v) for k, v in self._subscribers.items()}
        except Exception:
            return {}

# Глобальный bus для всего UI
event_bus = EventBus()
