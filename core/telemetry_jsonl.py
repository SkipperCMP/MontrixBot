from __future__ import annotations

from pathlib import Path
from typing import Optional
import json
import threading

from core.event_bus import Event, EventBus, get_event_bus

_LOCK = threading.RLock()
_INSTALLED = False


class JsonlEventSink:
    """Append-only JSONL sink for events (best-effort, never raises)."""
    def __init__(self, filepath: Path) -> None:
        self.filepath = Path(filepath)

    def handle(self, event: Event) -> None:
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":"))
            with _LOCK:
                with self.filepath.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception:
            return


def ensure_event_telemetry_installed(
    bus: Optional[EventBus] = None,
    *,
    log_path: str = "runtime/events.jsonl",
) -> None:
    """
    Idempotent. Installs a '*' subscriber that appends all events to JSONL.
    Safe to call from UI entrypoints and CLI tools.
    """
    global _INSTALLED
    try:
        with _LOCK:
            if _INSTALLED:
                return
            _INSTALLED = True

        b = bus or get_event_bus()
        sink = JsonlEventSink(Path(log_path))
        mirror_path = None
        try:
            # Backward-compat: also mirror to legacy runtime/logs/events.jsonl
            if str(log_path).replace("\\", "/").endswith("runtime/events.jsonl"):
                mirror_path = Path("runtime/logs/events.jsonl")
        except Exception:
            mirror_path = None
        mirror = JsonlEventSink(mirror_path) if mirror_path else None

        def _cb(ev: Event) -> None:
            sink.handle(ev)
            if mirror is not None:
                mirror.handle(ev)

        b.subscribe("*", _cb)

        # emit boot marker (best-effort)
        try:
            from core.event_bus import make_event
            b.publish(make_event("SYSTEM", {"msg": "event_telemetry_installed"}, actor="system"))
        except Exception:
            pass
    except Exception:
        return
