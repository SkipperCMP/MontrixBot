from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class ReadinessSeverity(str, Enum):
    OK = "OK"
    INFO = "INFO"
    WARNING = "WARNING"
    RISK = "RISK"


@dataclass(frozen=True)
class ReadinessFinding:
    """
    A read-only diagnostic finding.

    IMPORTANT:
    - Findings do NOT block anything.
    - Findings are not permissions.
    """
    severity: ReadinessSeverity
    code: str
    message: str
    metrics: Dict[str, Any]


@dataclass(frozen=True)
class ReadinessReport:
    """
    Read-only readiness report (diagnostic only).
    """
    findings: list[ReadinessFinding]
    metrics: Dict[str, Any]
