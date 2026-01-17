from __future__ import annotations

from core.event_bus import get_event_bus, make_event, new_cid, Event, EventBus
from core.telemetry_jsonl import ensure_event_telemetry_installed


def ensure_event_spine() -> EventBus:
    """
    Idempotent bootstrap:
    - ensures core event bus exists
    - installs JSONL telemetry sink
    """
    bus = get_event_bus()
    ensure_event_telemetry_installed(bus)
    return bus
