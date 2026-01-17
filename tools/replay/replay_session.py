from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any

from tools.replay.replay_types import ReplayConfig, TimelineEvent
from tools.replay.replay_result import ReplayResult
from tools.replay.readers_signals import read_signals_jsonl
from tools.replay.readers_policy_trace import read_policy_trace_jsonl
from tools.replay.replay_checkpoint import ReplayCheckpoint
from tools.replay.event_normalizer import EventNormalizer


@dataclass(frozen=True)
class ReplaySession:
    """
    Pure replay:
    - No side effects
    - No runtime access (imports / calls)
    - No UI / UIAPI
    - Deterministic: same inputs => same outputs
    """
    config: ReplayConfig

    def run(self) -> ReplayResult:
        # 1) Read raw events (best-effort)
        raw_events: List[TimelineEvent] = []

        if bool(self.config.include_signals):
            raw_events.extend(
                read_signals_jsonl(
                    self.config.root_dir,
                    strict_json=bool(self.config.strict_json),
                    max_events=self.config.max_events,
                )
            )
        if bool(getattr(self.config, "include_policy_trace", True)):
            raw_events.extend(
                read_policy_trace_jsonl(
                    self.config.root_dir,
                    strict_json=bool(self.config.strict_json),
                    max_events=self.config.max_events,
                )
            )

        # 2) Normalize (pass-through v1, but pipeline is now stable)
        normalizer = EventNormalizer()
        events_norm: List[TimelineEvent] = [normalizer.normalize(e) for e in raw_events]

        # 3) Deterministic ordering:
        # primary: ts, secondary: source, tertiary: seq
        events_sorted = sorted(events_norm, key=lambda e: (float(e.ts), str(e.source), int(e.seq)))

        # 4) Minimal checkpoints (read-only markers)
        checkpoints = self._build_checkpoints(events_sorted)

        stats: Dict[str, Any] = {
            "events_total": int(len(events_sorted)),
            "signals_total": int(sum(1 for e in events_sorted if e.type == "SIGNAL_RECORD")),
            "sources": sorted(list({str(e.source) for e in events_sorted})),
            "checkpoints_total": int(len(checkpoints)),
            "checkpoints": [
                {"index": int(c.index), "ts": float(c.ts), "label": str(c.label), "meta": dict(c.meta or {})}
                for c in checkpoints
            ],
        }
        return ReplayResult(events=events_sorted, stats=stats)

    @staticmethod
    def _build_checkpoints(events_sorted: List[TimelineEvent]) -> List[ReplayCheckpoint]:
        if not events_sorted:
            return [
                ReplayCheckpoint(index=0, ts=0.0, label="REPLAY_START", meta={"empty": True}),
                ReplayCheckpoint(index=0, ts=0.0, label="REPLAY_END", meta={"empty": True}),
            ]

        first = events_sorted[0]
        last = events_sorted[-1]
        return [
            ReplayCheckpoint(index=0, ts=float(first.ts), label="REPLAY_START", meta={"source": str(first.source)}),
            ReplayCheckpoint(index=int(len(events_sorted) - 1), ts=float(last.ts), label="REPLAY_END", meta={"source": str(last.source)}),
        ]
