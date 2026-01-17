from __future__ import annotations

from dataclasses import asdict
from typing import List, Dict, Any

from tools.replay.replay_types import TimelineEvent
from tools.replay.incident_types import Incident, IncidentLevel


class IncidentExtractor:
    """
    Best-effort incident extractor (v1).

    v1 policy:
    - Only detects obvious schema/quality issues (read-only).
    - Does NOT interpret trading outcomes.
    - Does NOT rely on runtime/core.
    """

    def extract(self, events: List[TimelineEvent]) -> List[Incident]:
        out: List[Incident] = []
        seq = 0

        for e in (events or []):
            # Rule 1: missing / zero timestamp
            if float(e.ts) == 0.0:
                out.append(
                    Incident(
                        level=IncidentLevel.WARNING,
                        code="REPLAY_TS_ZERO",
                        ts=float(e.ts),
                        message="Event has zero/unknown timestamp.",
                        context={"event_type": str(e.type), "source": str(e.source), "event_seq": int(e.seq)},
                        source="incident_extractor:v1",
                        seq=seq,
                    )
                )
                seq += 1

            # Rule 2: unknown event type
            if str(e.type).strip() in ("", "UNKNOWN"):
                out.append(
                    Incident(
                        level=IncidentLevel.WARNING,
                        code="REPLAY_EVENT_TYPE_UNKNOWN",
                        ts=float(e.ts),
                        message="Event type is unknown/empty.",
                        context={"source": str(e.source), "event_seq": int(e.seq)},
                        source="incident_extractor:v1",
                        seq=seq,
                    )
                )
                seq += 1

            # Rule 3: malformed signal record shape (very conservative)
            if str(e.type) == "SIGNAL_RECORD":
                payload = dict(e.payload or {})
                # Expect dict with at least 'ts' (best-effort) and something identifying the signal
                if not isinstance(payload, dict) or len(payload) == 0:
                    out.append(
                        Incident(
                            level=IncidentLevel.RISK,
                            code="SIGNAL_RECORD_EMPTY",
                            ts=float(e.ts),
                            message="Signal record payload is empty or invalid.",
                            context={"source": str(e.source), "event_seq": int(e.seq)},
                            source="incident_extractor:v1",
                            seq=seq,
                        )
                    )
                    seq += 1

        # Deterministic ordering (same as replay)
        return sorted(out, key=lambda i: (float(i.ts), str(i.source), int(i.seq)))

    @staticmethod
    def to_dict_list(incidents: List[Incident]) -> List[Dict[str, Any]]:
        return [
            {
                "level": str(i.level.value),
                "code": str(i.code),
                "ts": float(i.ts),
                "message": str(i.message),
                "source": str(i.source),
                "seq": int(i.seq),
                "context": dict(i.context or {}),
            }
            for i in (incidents or [])
        ]
