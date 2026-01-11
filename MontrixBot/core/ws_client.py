
from __future__ import annotations
from typing import Callable, Optional

class WSClient:
    """Интерфейс WS клиента (реализацию сети добавим позже)."""
    def __init__(self) -> None:
        self._on_tick: Optional[Callable[[dict], None]] = None
        self._on_error: Optional[Callable[[Exception], None]] = None
        self._connected: bool = False

    def on_tick(self, cb: Callable[[dict], None]) -> None:
        self._on_tick = cb

    def on_error(self, cb: Callable[[Exception], None]) -> None:
        self._on_error = cb

    def connect(self) -> None:
        self._connected = True

    def close(self) -> None:
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected
