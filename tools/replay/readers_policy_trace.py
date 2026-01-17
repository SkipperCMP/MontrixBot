from __future__ import annotations

import json
from pathlib import Path
from typing import List

from tools.replay.replay_types import TimelineEvent


def read_policy_trace_jsonl(root_dir: str, *, strict_json: bool = False, max_events: int | None = None) -> List[TimelineEvent]:
    """
    Reads runtime/policy_trace.jsonl and returns timeline events.
    Determinism: seq assigned by read order.
    """
    root = Path(root_dir)
    path = root / "runtime" / "policy_trace.jsonl"
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

            ts = rec.get("ts")
            try:
                ts_f = float(ts) if ts is not None else 0.0
            except Exception:
                ts_f = 0.0

            out.append(
                TimelineEvent(
                    ts=ts_f,
                    type="POLICY_TRACE_EVENT",
                    payload=rec,
                    source="runtime/policy_trace.jsonl",
                    seq=seq,
                )
            )
            seq += 1

    return out
