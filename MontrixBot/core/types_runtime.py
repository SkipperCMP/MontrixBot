from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import List, Optional, Dict, Any


class TradingState(str, Enum):
    TRADING_ACTIVE = "TRADING_ACTIVE"
    AUTO_PAUSED = "AUTO_PAUSED"
    HARD_STOPPED = "HARD_STOPPED"


class AutonomyMode(str, Enum):
    MANUAL_ONLY = "MANUAL_ONLY"
    AUTO_ALLOWED = "AUTO_ALLOWED"


@dataclass(frozen=True)
class GateDecision:
    """
    GateEngine verdict (dry in v2.2.0)
    decision: "ALLOW" | "VETO"
    reasons: stable codes/strings
    evidence: string refs only (no objects)
    """
    decision: str
    reasons: List[str]
    evidence: List[str]


@dataclass(frozen=True)
class StatusPayload:
    is_trading: bool
    state: str
    mode: str
    why_not: List[str]
    open_position: Optional[Dict[str, Any]]
    gate: Optional[GateDecision] = None
    ts_utc: Optional[str] = None  # ISO-8601 UTC timestamp (read-only diagnostics)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

