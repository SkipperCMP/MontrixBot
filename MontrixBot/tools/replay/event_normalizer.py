from __future__ import annotations

from dataclasses import replace
from typing import Optional

from tools.replay.replay_types import TimelineEvent


class EventNormalizer:
    """
    Pass-through normalizer (v1).

    Purpose:
    - keep replay pipeline structure stable
    - allow future normalization without changing readers/session wiring

    Rules (v1):
    - Never adds semantics
    - Never changes payload meaning
    - Best-effort: if something is malformed, keep it stable
    """

    def normalize(self, event: TimelineEvent) -> TimelineEvent:
        ts = self._safe_float(event.ts, default=0.0)
        seq = int(event.seq) if event.seq is not None else 0
        etype = str(event.type) if event.type is not None else "UNKNOWN"
        source = str(event.source) if event.source is not None else "unknown"
        payload = dict(event.payload or {})

        # Keep immutability + stable shape
        return replace(
            event,
            ts=ts,
            seq=seq,
            type=etype,
            source=source,
            payload=payload,
        )

    @staticmethod
    def _safe_float(v: object, *, default: float) -> float:
        try:
            return float(v)  # type: ignore[arg-type]
        except Exception:
            return float(default)
