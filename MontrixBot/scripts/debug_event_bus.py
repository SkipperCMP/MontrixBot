# scripts/debug_event_bus.py
from __future__ import annotations

import os
import sys
import time

# Добавляем корень проекта в sys.path, чтобы импортировать ui.*
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from ui.events.bus import event_bus  # noqa: E402
from ui.events.types import Event, EVT_SNAPSHOT  # noqa: E402


def _format_snapshot_summary(snapshot: dict | None) -> str:
    snapshot = snapshot or {}
    version = snapshot.get("version") or snapshot.get("state_version")
    positions = snapshot.get("positions") or {}
    if isinstance(positions, dict):
        positions_count = len(positions)
    else:
        positions_count = None
    return f"version={version!r}, positions={positions_count}"


def on_snapshot(event: Event) -> None:
    summary = _format_snapshot_summary(event.payload.get("snapshot"))
    print(f"[EVT] snapshot ts={event.ts:.3f} :: {summary}")


def main() -> None:
    print("[debug_event_bus] Subscribing to EVT_SNAPSHOT...")
    event_bus.subscribe(EVT_SNAPSHOT, on_snapshot)
    print("[debug_event_bus] Waiting for events. Press Ctrl+C to exit.")
    try:
        while True:
            # Небольшой sleep, чтобы не жечь CPU
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[debug_event_bus] Unsubscribing and exiting...")

        # STEP1.3.4_pre3 — EventBus subscribers diagnostics
        try:
            print("[EventBus] stats:", event_bus.stats())
        except Exception:
            pass

        event_bus.unsubscribe(EVT_SNAPSHOT, on_snapshot)


if __name__ == "__main__":
    main()
