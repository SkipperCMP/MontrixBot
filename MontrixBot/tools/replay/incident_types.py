from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class IncidentLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    RISK = "RISK"
    PANIC = "PANIC"


@dataclass(frozen=True)
class Incident:
    """
    Read-only incident fact.

    IMPORTANT:
    - Incidents never trigger actions.
    - Incidents never change replay output.
    """
    level: IncidentLevel
    code: str
    ts: float
    message: str
    context: Dict[str, Any]
    source: str = "replay"
    seq: int = 0  # stable tie-breaker
