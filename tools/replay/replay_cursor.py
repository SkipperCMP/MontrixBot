from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReplayCursor:
    """
    Forward-only cursor over a timeline.
    """
    index: int = 0

    def next(self) -> "ReplayCursor":
        return ReplayCursor(index=int(self.index) + 1)
