# ui/services/tick_updater.py
from __future__ import annotations

from typing import Any
import time

from ui.events.bus import event_bus
from ui.events.types import Event, EVT_SNAPSHOT


class TickUpdater:
    """Лёгкий TickService / Update Router для UI.

    STEP1.3.1 (pre9): ранняя версия tick-сервиса.

    Задачи текущей версии:
    - Подвеситься к SnapshotService и получать снапшот ядра;
    - Фильтровать лишние обновления (по версии снапшота);
    - Предоставить единое место, куда позже можно будет
      повесить обновление графиков, прайса и любых tick-виджетов.

    Важно: здесь НЕТ собственного цикла `after`, мы живём
    внутри общего UIRefreshService → SnapshotService.
    """

    def __init__(self, app: Any) -> None:
        self.app = app
        self._last_version: str | int | None = None

    # ------------------------------------------------------------------ API --

    def update_from_snapshot(self, snapshot: dict | None) -> None:
        """Получает снапшот ядра и раздаёт его tick-чувствительным виджетам.

        Сейчас реализовано только:
        - простая дедупликация по version/state_version;
        - безопасные вызовы потенциальных хендлеров, если они есть.
        """

        app = self.app
        snapshot = snapshot or {}

        # --- dedupe по версии снапшота, чтобы не дёргать UI без надобности
        version = None
        try:
            version = snapshot.get("version") or snapshot.get("state_version")
        except Exception:
            version = None

        if version is not None and version == self._last_version:
            # ничего нового, можно тихо выйти
            return

        self._last_version = version

        # --- публикуем EVT_SNAPSHOT в EventBus (Unified Event System, STEP1.3.4)
        try:
            event = Event(
                type=EVT_SNAPSHOT,
                ts=time.time(),
                source="TickUpdater",
                payload={"snapshot": snapshot},
            )
            event_bus.publish(event)
        except Exception:
            # проблемы в EventBus не должны ломать основной tick-пайплайн
            pass


        # сюда позже можно добавить:
        # - обновление inline heatmap по ticks
        # - отдельные мини-виджеты/индикаторы по тикам
