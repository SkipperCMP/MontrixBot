from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any

from tools.replay.replay_types import TimelineEvent


def read_signals_jsonl(root_dir: str, *, strict_json: bool = False, max_events: int | None = None) -> List[TimelineEvent]:
    """
    Reads runtime/signals.jsonl and returns timeline events.

    Source of truth:
    - core/signal_store.py writes JSONL records into runtime/signals.jsonl

    Determinism:
    - seq is assigned by read order (stable).
    """
    root = Path(root_dir)
    path = root / "runtime" / "signals.jsonl"
    if not path.exists():
        return []

    out: List[TimelineEvent] = []
    seq = 0

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if max_events is not None and len(out) >= int(max_events):
                break

            s = (line or "").strip()
            if not s:
                continue

            try:
                rec = json.loads(s)
            except Exception:
                if strict_json:
                    raise
                continue

            if not isinstance(rec, dict):
                continue

            # best-effort timestamp extraction
            ts = rec.get("ts")
            try:
                ts_f = float(ts) if ts is not None else 0.0
            except Exception:
                ts_f = 0.0

            out.append(
                TimelineEvent(
                    ts=ts_f,
                    type="SIGNAL_RECORD",
                    payload=rec,
                    source="runtime/signals.jsonl",
                    seq=seq,
                )
            )
            seq += 1

    return out
