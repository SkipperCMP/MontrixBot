from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, Any, Optional
import threading
import time

from .events import StateSnapshot, StatePatch, Heartbeat, ReconnectSignal


@dataclass
class BinderMetrics:
    """
    Небольшая статистика по работе биндерa — может пригодиться
    для отладки/мониторинга в будущем.
    """
    ui_version: int = 0
    missed_patches: int = 0
    forced_snapshots: int = 0
    last_resync_ms: int = 0


class StateBinder:
    """
    Универсальный помощник для поддержки локальной (UI) копии состояния ядра.

    Работает с тремя примитивными типами событий:

    * StateSnapshot: полный дамп состояния (version + payload)
    * StatePatch: инкрементальные изменения между версиями
    * Heartbeat: периодический пинг «я жив» с текущей версией

    Binder ничего не знает о структуре payload — он просто хранит
    произвольный вложенный dict и применяет операции "set" по
    точечным путям.
    """

    def __init__(
        self,
        snapshot_provider: Optional[Callable[[], StateSnapshot]] = None,
        patch_callback: Optional[Callable[[StatePatch], None]] = None,
        on_resync: Optional[Callable[[StateSnapshot], None]] = None,
    ) -> None:
        self._snapshot_provider = snapshot_provider
        self._patch_callback = patch_callback
        self._on_resync = on_resync

        self._lock = threading.RLock()
        self._ui_state_snapshot: Dict[str, Any] = {}
        self._ui_version: int = 0
        self.metrics = BinderMetrics()

    # ---------- конфигурация ----------

    def set_snapshot_provider(self, provider: Callable[[], StateSnapshot]) -> None:
        """Задать функцию, которая выдаёт полный снапшот состояния."""
        self._snapshot_provider = provider

    def set_patch_callback(self, callback: Optional[Callable[[StatePatch], None]]) -> None:
        """Коллбек, который вызывается после успешного применения патча."""
        self._patch_callback = callback

    def set_on_resync(self, callback: Optional[Callable[[StateSnapshot], None]]) -> None:
        """Коллбек, который вызывается после полной пересинхронизации."""
        self._on_resync = callback

    # ---------- публичное чтение ----------

    def get_ui_state(self) -> Dict[str, Any]:
        """
        Вернуть текущий UI-снапшот.

        Возвращается неглубокая копия, чтобы вызывающий код случайно
        не испортил внутреннее состояние биндерa.
        """
        with self._lock:
            return dict(self._ui_state_snapshot)

    # ---------- обработка событий ----------

    def init_or_resync(self) -> None:
        """
        Принудительная полная синхронизация.

        Можно вызывать на старте или когда стало понятно, что поток
        патчей рассинхронизировался.
        """
        if self._snapshot_provider is None:
            return

        with self._lock:
            snap = self._snapshot_provider()
            self._ui_state_snapshot = dict(snap.payload or {})
            self._ui_version = int(snap.version)
            self.metrics.ui_version = self._ui_version
            self.metrics.forced_snapshots += 1
            self.metrics.last_resync_ms = int(time.time() * 1000)

        if self._on_resync:
            self._on_resync(snap)

    def on_heartbeat(self, hb: Heartbeat) -> None:
        """
        Обработка heartbeat от ядра.

        Если версия в heartbeat больше, чем текущая UI-версия — значит,
        мы пропустили хотя бы один патч и нужно сделать полную пересинхру.
        """
        if self._snapshot_provider is None:
            return

        with self._lock:
            if hb.version > self._ui_version:
                self.metrics.missed_patches += 1
                self._force_snapshot_locked()
            # Версию по heartbeat специально не двигаем.

    def on_patch(self, patch: StatePatch) -> None:
        """
        Применить инкрементальный патч к текущему UI-состоянию.

        Формат операции:
            {"op": "set", "path": "portfolio.equity", "value": 123.45}

        Если последовательность нарушена (from_version != ui_version),
        биндер делает полную пересинхронизацию.
        """
        if self._snapshot_provider is None:
            return

        with self._lock:
            if patch.from_version != self._ui_version:
                # Потеряли часть патчей — пересинхронизируемся.
                self.metrics.missed_patches += 1
                self._force_snapshot_locked()
                return

            for op in patch.ops or []:
                if not isinstance(op, dict):
                    continue
                if op.get("op") != "set":
                    # В будущем можно добавить "del" и т.п.
                    continue

                path_raw = op.get("path")
                if not path_raw:
                    continue
                path = str(path_raw).split(".")

                target: Dict[str, Any] = self._ui_state_snapshot
                for key in path[:-1]:
                    if key not in target or not isinstance(target[key], dict):
                        target[key] = {}
                    target = target[key]
                target[path[-1]] = op.get("value")

            self._ui_version = int(patch.to_version)
            self.metrics.ui_version = self._ui_version

        if self._patch_callback:
            self._patch_callback(patch)

    def on_reconnect(self, rc: ReconnectSignal) -> None:
        """
        Обработка сигнала переподключения (например, после reconenct WebSocket).

        Сейчас просто делаем полную пересинхронизацию.
        """
        self.init_or_resync()

    # ---------- внутренние помощники ----------

    def _force_snapshot_locked(self) -> None:
        """
        То же, что init_or_resync, но вызывается при уже захваченном lock.
        """
        if self._snapshot_provider is None:
            return

        snap = self._snapshot_provider()
        self._ui_state_snapshot = dict(snap.payload or {})
        self._ui_version = int(snap.version)
        self.metrics.ui_version = self._ui_version
        self.metrics.forced_snapshots += 1
        self.metrics.last_resync_ms = int(time.time() * 1000)

        if self._on_resync:
            self._on_resync(snap)
