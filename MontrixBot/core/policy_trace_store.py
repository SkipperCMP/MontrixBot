from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from core.system_clock import SystemClock
from core.schema_ids import SchemaIds, SchemaVersions
from core.policy_trace import PolicyDecision, PolicyTraceEvent


class PolicyTraceStore:
    """
    Append-only policy trace store (runtime/policy_trace.jsonl).

    HARD RULES:
    - best-effort I/O
    - no exceptions should bubble up
    - no gating / no actions
    """

    @staticmethod
    def _runtime_dir(root: Optional[Path] = None) -> Path:
        base = root if isinstance(root, Path) else Path(__file__).resolve().parents[1]
        return base / "runtime"

    @staticmethod
    def _path(root: Optional[Path] = None) -> Path:
        return PolicyTraceStore._runtime_dir(root) / "policy_trace.jsonl"

    @staticmethod
    def append(
        policy: str,
        decision: PolicyDecision,
        reason_code: str,
        *,
        details: Optional[Dict[str, Any]] = None,
        scope: str = "unknown",
        source: str = "core",
        root: Optional[Path] = None,
        seq: int = 0,
    ) -> None:
        try:
            path = PolicyTraceStore._path(root)
            path.parent.mkdir(parents=True, exist_ok=True)

            rec: Dict[str, Any] = {
                "_schema": {"name": SchemaIds.POLICY_TRACE_EVENT, "version": SchemaVersions.V1},
                "ts": SystemClock.now_wall_ts(),
                "_clock": SystemClock.meta_dict(),
                "policy": str(policy),
                "decision": str(decision.value),
                "reason_code": str(reason_code),
                "details": dict(details or {}),
                "scope": str(scope),
                "source": str(source),
                "seq": int(seq),
            }

            line = json.dumps(rec, ensure_ascii=False)
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            # best-effort only
            return
