from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.types_runtime import GateDecision


@dataclass(frozen=True)
class GateContext:
    """
    Read-only context for Gate evaluation.

    v2.2.4:
      - evidence enrichment via string refs
      - no side effects
      - no execution control
    """
    mode: str
    state: str
    is_trading: bool
    open_position: Optional[Dict[str, Any]]

    # evidence inputs (read-only)
    policy_hard_stop_active: bool
    fsm_pause_reasons: List[str]
    why_not: List[str]

    # enrichment refs (strings only)
    status_ts: int
    policy_file_ref: str
    fsm_file_ref: str


def _norm(v: Any) -> str:
    s = str(v)
    s = s.replace("\n", " ").replace("\r", " ").strip()
    return s if s else "-"


def _join(items: List[str]) -> str:
    xs = [_norm(x) for x in (items or []) if _norm(x) != "-"]
    return ",".join(xs) if xs else "-"


def _dedup_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in items or []:
        s = str(x)
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


class GateEngine:
    """
    STEP 2.0 — GateEngine

    v2.2.4 scope (still read-only):
      - evaluate(ctx) -> GateDecision(decision, reasons, evidence)
      - decision is DRY ONLY (status payload), MUST NOT control execution
      - evidence: namespaced string refs, deterministic ordering
      - enrichment: add file refs + status ts (string refs only)
    """

    REASON_HARD_STOP = "HARD_STOP"
    REASON_AUTO_PAUSED = "AUTO_PAUSED"

    def evaluate(self, ctx: GateContext) -> GateDecision:
        # Deterministic evidence ordering (do not reorder without a version bump)
        evidence: List[str] = [
            f"status:ts={int(ctx.status_ts)}",
            f"policy:file={_norm(ctx.policy_file_ref)}",
            f"fsm:file={_norm(ctx.fsm_file_ref)}",
            f"policy:mode={_norm(ctx.mode)}",
            f"policy:hard_stop_active={str(bool(ctx.policy_hard_stop_active)).lower()}",
            f"fsm:state={_norm(ctx.state)}",
            f"fsm:pause_reasons={_join(ctx.fsm_pause_reasons)}",
            f"status:why_not={_join(ctx.why_not)}",
            f"position:open={'1' if ctx.open_position else '0'}",
        ]

        # Dry rules (independent of why_not)
        rule_reasons: List[str] = []
        if bool(ctx.policy_hard_stop_active) or _norm(ctx.state) == "HARD_STOPPED":
            rule_reasons.append(self.REASON_HARD_STOP)
        if _norm(ctx.state) == "AUTO_PAUSED":
            rule_reasons.append(self.REASON_AUTO_PAUSED)

        merged_reasons = _dedup_keep_order(list(ctx.why_not or []) + rule_reasons)

        if merged_reasons:
            return GateDecision(decision="VETO", reasons=merged_reasons, evidence=evidence)

        return GateDecision(decision="ALLOW", reasons=[], evidence=evidence)
