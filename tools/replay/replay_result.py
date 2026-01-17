from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any

from tools.replay.replay_types import TimelineEvent


@dataclass(frozen=True)
class ReplayResult:
    """
    Replay output (read-only).
    """
    events: List[TimelineEvent]
    stats: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stats": dict(self.stats or {}),
            "events": [
                {
                    "ts": float(e.ts),
                    "type": str(e.type),
                    "source": str(e.source),
                    "seq": int(e.seq),
                    "payload": dict(e.payload or {}),
                }
                for e in (self.events or [])
            ],
        }
