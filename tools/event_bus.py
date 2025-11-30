
from __future__ import annotations
from typing import Callable, Dict, List, Any
import threading

class _EventBus:
    def __init__(self) -> None:
        self._subs: Dict[str, List[Callable[[Any], None]]] = {}
        self._lock = threading.RLock()

    def subscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        with self._lock:
            self._subs.setdefault(topic, []).append(handler)

    def publish(self, topic: str, payload: Any) -> None:
        with self._lock:
            handlers = list(self._subs.get(topic, []))
        # call outside lock
        for h in handlers:
            try:
                h(payload)
            except Exception:
                # handlers must be resilient
                pass

EventBus = _EventBus()
