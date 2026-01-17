from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    VETO = "VETO"
    SKIP = "SKIP"


@dataclass(frozen=True)
class PolicyTraceEvent:
    """
    Read-only policy trace event.

    IMPORTANT:
    - This is observability only.
    - Must not trigger actions.
    - Must not be used as permission.
    """
    ts: float
    policy: str
    decision: PolicyDecision
    reason_code: str
    details: Dict[str, Any]
    scope: str = "unknown"   # e.g., "REAL", "SIM", "ORDER", "TPSL"
    source: str = "core"
    seq: int = 0
