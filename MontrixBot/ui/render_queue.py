
from __future__ import annotations
import time
from typing import Callable

class RenderQueue:
    """
    Simple coalescing render scheduler:
      - signal() marks a pending render
      - try_render(fn) executes at most once per min_interval
      - multiple signals within interval are coalesced into one render
    """
    def __init__(self, max_fps: int = 30):
        self.min_interval = 1.0 / max_fps if max_fps > 0 else 0.033
        self._last = 0.0
        self._pending = False

    def signal(self) -> None:
        self._pending = True

    def try_render(self, render_fn: Callable[[], None]) -> None:
        now = time.time()
        if not self._pending:
            return
        if now - self._last < self.min_interval:
            return
        self._pending = False
        self._last = now
        render_fn()
