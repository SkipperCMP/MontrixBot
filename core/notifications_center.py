from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Callable
import time
import threading
import logging

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class NotificationEvent:
    """
    Minimal, transport-agnostic notification event.

    IMPORTANT:
    - This is OBSERVABILITY-only. It must not imply trading actions.
    - message is human-readable; meta is optional structured context.
    """
    ts: float
    level: str  # "INFO" | "WARNING" | "ERROR"
    topic: str  # e.g. "panic" | "safe" | "system" | "data" | "executor"
    message: str
    meta: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def now(level: str, topic: str, message: str, meta: Optional[Dict[str, Any]] = None) -> "NotificationEvent":
        return NotificationEvent(
            ts=float(time.time()),
            level=str(level or "INFO").upper(),
            topic=str(topic or "system"),
            message=str(message or ""),
            meta=dict(meta or {}),
        )


class NotificationSink(Protocol):
    """
    Sink interface. Must be best-effort and must never raise.
    """
    def handle(self, event: NotificationEvent) -> None:
        ...


class NotificationCenter:
    """
    Central notification bus (best-effort).

    Guarantees:
    - emit() never raises
    - sink failures do not affect others
    - thread-safe for registration + emission

    NOTE:
    - No dedupe / TTL here yet. That belongs to later patches (v1.7.0-03).
    """
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sinks: List[NotificationSink] = []

    def register_sink(self, sink: NotificationSink) -> None:
        try:
            if sink is None:
                return
            with self._lock:
                self._sinks.append(sink)
        except Exception:
            # never break caller
            return

    def clear_sinks(self) -> None:
        try:
            with self._lock:
                self._sinks = []
        except Exception:
            return

    def emit(self, event: NotificationEvent) -> None:
        """
        Best-effort emit to all sinks.
        """
        try:
            if event is None:
                return
        except Exception:
            return

        try:
            with self._lock:
                sinks = list(self._sinks)
        except Exception:
            sinks = []

        for s in sinks:
            try:
                s.handle(event)
            except Exception:
                # sink must not break the bus
                continue

    def emit_now(self, level: str, topic: str, message: str, meta: Optional[Dict[str, Any]] = None) -> None:
        try:
            self.emit(NotificationEvent.now(level=level, topic=topic, message=message, meta=meta))
        except Exception:
            return


# ---- singleton (core-owned) ----

_NOTIFY_SINGLETON: Optional[NotificationCenter] = None
_NOTIFY_LOCK = threading.RLock()


def get_notification_center() -> NotificationCenter:
    """
    Core-owned singleton.
    IMPORTANT: must never raise.
    """
    global _NOTIFY_SINGLETON
    try:
        with _NOTIFY_LOCK:
            if _NOTIFY_SINGLETON is None:
                _NOTIFY_SINGLETON = NotificationCenter()

                # Best-effort: attach default LogSink once.
                try:
                    from core.notification_sinks import LogSink

                    _NOTIFY_SINGLETON.register_sink(LogSink())
                except Exception:
                    pass

            return _NOTIFY_SINGLETON
    except Exception:
        # last resort: return a new instance, still best-effort
        return NotificationCenter()
