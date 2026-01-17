from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class DecisionResult:
    decision: str  # ENTER | EXIT | HOLD
    reasons: List[str]
    meta: Dict[str, Any]


def decide_intent(
    *,
    signal_side: str,
    has_open_position: bool,
    allow_entry: bool,
    prefer_noop: bool = True,
) -> DecisionResult:
    """Deterministic intent decision.

    Rules (minimal, stable):
    - Default is HOLD (prefer_noop=True).
    - ENTER only if signal_side == BUY, no open position, and allow_entry.
    - EXIT only if signal_side == SELL and has open position.
    """

    ss = str(signal_side or "HOLD").upper().strip()
    reasons: List[str] = []
    meta: Dict[str, Any] = {
        "signal_side": ss,
        "has_open_position": bool(has_open_position),
        "allow_entry": bool(allow_entry),
    }

    # Prefer no-op by default
    if prefer_noop and ss not in ("BUY", "SELL"):
        return DecisionResult(decision="HOLD", reasons=["PREFER_NOOP"], meta=meta)

    if ss == "BUY":
        if has_open_position:
            reasons.append("POSITION_ALREADY_OPEN")
            return DecisionResult(decision="HOLD", reasons=reasons, meta=meta)
        if not allow_entry:
            reasons.append("ENTRY_BLOCKED")
            return DecisionResult(decision="HOLD", reasons=reasons, meta=meta)
        return DecisionResult(decision="ENTER", reasons=reasons, meta=meta)

    if ss == "SELL":
        if not has_open_position:
            reasons.append("NO_OPEN_POSITION")
            return DecisionResult(decision="HOLD", reasons=reasons, meta=meta)
        return DecisionResult(decision="EXIT", reasons=reasons, meta=meta)

    return DecisionResult(
        decision="HOLD",
        reasons=reasons or (["PREFER_NOOP"] if prefer_noop else []),
        meta=meta,
    )
