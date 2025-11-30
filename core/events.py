from __future__ import annotations
from dataclasses import dataclass
from typing import Any, List, Dict
import time


@dataclass
class Heartbeat:
    """
    Лёгкий сигнал-живости от ядра с текущей версией состояния.

    Конкретный смысл version задаётся продюсером, но StateBinder
    предполагает, что это монотонно растущие целые числа.
    """
    version: int
    ts: float | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "HEARTBEAT",
            "version": int(self.version),
            "ts": float(self.ts or time.time()),
        }


@dataclass
class StateSnapshot:
    """
    Полный снапшот состояния ядра.

    payload — произвольный вложенный dict, представляющий UI-видимое
    состояние. StateBinder относится к нему как к «чёрному ящику».
    """
    version: int
    payload: Dict[str, Any]
    ts: float | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "STATE_SNAPSHOT",
            "version": int(self.version),
            "ts": float(self.ts or time.time()),
            "payload": self.payload,
        }


@dataclass
class StatePatch:
    """
    Инкрементальное обновление между двумя версиями состояния.

    ops — список операций. Сейчас поддерживается только "set"
    с точечными путями, например:
        {"op": "set", "path": "portfolio.equity", "value": 123.45}
    """
    from_version: int
    to_version: int
    ops: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "STATE_PATCH",
            "from_version": int(self.from_version),
            "to_version": int(self.to_version),
            "ops": list(self.ops),
        }


@dataclass
class ReconnectSignal:
    """
    Сигнал о том, что транспортный слой переподключился, и UI
    нужно пересинхронизировать состояние.
    """
    reason: str = "ws_reconnect"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "RECONNECT",
            "reason": str(self.reason or "ws_reconnect"),
        }
