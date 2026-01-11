from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class ReplayCheckpoint:
    """
    A read-only marker in the replay timeline.

    IMPORTANT:
    - No semantics, no decisions, no actions.
    - Used only for observability / debugging / report structure.
    """
    index: int
    ts: float
    label: str
    meta: Dict[str, Any]
