from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List
import logging
import threading
import json
from pathlib import Path

from core.notifications_center import NotificationEvent

log = logging.getLogger(__name__)


@dataclass
class LogSink:
    """
    Writes notifications into python logging.

    Best-effort. Never raises.
    """
    logger_name: str = "montrix.notifications"

    def handle(self, event: NotificationEvent) -> None:
        try:
            lg = logging.getLogger(self.logger_name)
            level = str(getattr(event, "level", "INFO") or "INFO").upper()
            topic = str(getattr(event, "topic", "system") or "system")
            msg = str(getattr(event, "message", "") or "")

            # meta: include only if present
            meta = getattr(event, "meta", None)
            if isinstance(meta, dict) and meta:
                msg = f"[{topic}] {msg} meta={meta}"
            else:
                msg = f"[{topic}] {msg}"

            if level == "ERROR":
                lg.error(msg)
            elif level == "WARNING":
                lg.warning(msg)
            else:
                lg.info(msg)
        except Exception:
            return


class NullSink:
    """
    No-op sink.
    """
    def handle(self, event: NotificationEvent) -> None:
        return


class MemorySink:
    """
    In-memory bounded history for future UI read-only visibility.

    NOTE:
    - Not used by default in v1.7.0-01
    - Safe to keep for future patches (history, inspection, tests)
    """
    def __init__(self, maxlen: int = 500) -> None:
        self._lock = threading.RLock()
        self._maxlen = int(maxlen or 500)
        self._items: List[NotificationEvent] = []

    def handle(self, event: NotificationEvent) -> None:
        try:
            with self._lock:
                self._items.append(event)
                if len(self._items) > self._maxlen:
                    del self._items[:-self._maxlen]
        except Exception:
            return

    def snapshot(self) -> list[NotificationEvent]:
        try:
            with self._lock:
                return list(self._items)
        except Exception:
            return []

class JsonlNotificationSink:
    """
    Append-only JSONL sink for notification events.

    - Core-owned
    - Best-effort
    - Never raises
    - Writes to runtime/notifications.jsonl
    """

    def __init__(self, path: str = "runtime/notifications.jsonl") -> None:
        self._path = Path(path)
        self._lock = threading.RLock()

    def handle(self, event: NotificationEvent) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)

            meta = {}
            if isinstance(getattr(event, "meta", None), dict):
                meta = dict(event.meta)

            data = {
                "ts": float(getattr(event, "ts", 0.0)),
                "level": str(getattr(event, "level", "INFO")),
                "topic": str(getattr(event, "topic", "system")),
                "message": str(getattr(event, "message", "")),
                "meta": meta,
            }

            line = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

            with self._lock:
                with self._path.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception:
            # notifications must never break runtime
            return
