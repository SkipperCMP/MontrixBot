from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class TimelineEvent:
    """
    A single immutable fact in time.

    IMPORTANT:
    - No semantics, no decisions, no actions.
    - Read-only representation of something that happened.
    """
    ts: float
    type: str
    payload: Dict[str, Any]
    source: str = "unknown"
    seq: int = 0  # stable tie-breaker for determinism


@dataclass(frozen=True)
class ReplayConfig:
    """
    Replay configuration.

    root_dir: project root (where /runtime sits)
    """
    root_dir: str
    include_signals: bool = True
    strict_json: bool = False  # if True: invalid lines raise; else skipped best-effort
    max_events: Optional[int] = None
    include_policy_trace: bool = True
