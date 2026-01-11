from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ScoutNote:
    ts: float
    side: str              # BUY / SELL / HOLD
    confidence: float
    priority: str          # INFO / WARNING / RISK
    reason: str
    meta: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ts": float(self.ts),
            "side": str(self.side),
            "confidence": float(self.confidence),
            "priority": str(self.priority),
            "reason": str(self.reason),
            "meta": dict(self.meta or {}),
        }


class ScoutNotesHygiene:
    """
    SIM-only hygiene layer for advisor recommendations.

    Responsibilities:
    - TTL filtering
    - deduplication (same side+reason)
    - priority classification

    IMPORTANT:
    - no trading logic
    - no persistence
    - best-effort
    """

    def __init__(self, ttl_sec: float = 10.0) -> None:
        self._ttl = float(ttl_sec)
        self._last_fp: Optional[str] = None
        self._last_ts: float = 0.0

    def _fingerprint(self, side: str, reason: str) -> str:
        h = hashlib.sha1()
        h.update(str(side).encode("utf-8"))
        h.update(str(reason).encode("utf-8"))
        return h.hexdigest()

    def classify_priority(self, confidence: float) -> str:
        c = float(confidence or 0.0)
        if c >= 0.7:
            return "RISK"
        if c >= 0.4:
            return "WARNING"
        return "INFO"

    def process(
        self,
        side: str,
        confidence: float,
        reason: str,
        meta: Optional[Dict[str, Any]] = None,
        now_ts: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Returns a plain dict (UI/snapshot-friendly) or None (dropped by hygiene).
        """
        try:
            ts = float(now_ts or time.time())
            fp = self._fingerprint(side, reason)

            # TTL + dedupe: drop identical note if within TTL window
            if self._last_fp == fp and (ts - float(self._last_ts or 0.0)) < self._ttl:
                return None

            self._last_fp = fp
            self._last_ts = ts

            note = ScoutNote(
                ts=ts,
                side=str(side),
                confidence=float(confidence or 0.0),
                priority=self.classify_priority(float(confidence or 0.0)),
                reason=str(reason),
                meta=dict(meta or {}),
            )
            return note.as_dict()
        except Exception:
            return None
