from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from tools.replay.replay_result import ReplayResult
from tools.replay.incident_types import Incident
from tools.replay.readiness_types import ReadinessFinding, ReadinessReport, ReadinessSeverity

import json
from core.runtime_state import load_runtime_state
from core.policy_trace_store import PolicyTraceStore


@dataclass(frozen=True)
class ReadinessRunner:
    """
    Readiness runner (v1).

    IMPORTANT:
    - Read-only diagnostics.
    - No gating. No permissions. No actions.
    """
    root_dir: str

    def run(self, replay: ReplayResult, incidents: List[Incident]) -> ReadinessReport:
        findings: List[ReadinessFinding] = []

        # --- core metrics
        events = replay.events or []
        events_total = int(len(events))
        incidents_total = int(len(incidents or []))

        # --- runtime/meta diagnostics (REAL blockers, read-only)
        runtime_state = load_runtime_state() or {}
        meta = runtime_state.get("meta") or {}

        strategy_state = meta.get("strategy_state")
        trading_gate = meta.get("trading_gate")
        safe_boot_reason = meta.get("safe_boot_reason")
        safe_boot_ts = meta.get("safe_boot_ts")

        real_blockers = []
        if trading_gate != "ALLOW":
            real_blockers.append("TRADING_GATE")
        if strategy_state == "PAUSED":
            real_blockers.append("STRATEGY_PAUSED")
        if safe_boot_reason:
            real_blockers.append("SAFE_BOOT")

        findings.append(
            ReadinessFinding(
                severity=ReadinessSeverity.INFO if real_blockers else ReadinessSeverity.OK,
                code="READINESS_REAL_BLOCKERS",
                message="Current REAL trading blockers (diagnostic only).",
                metrics={
                    "trading_gate": trading_gate,
                    "strategy_state": strategy_state,
                    "safe_boot_reason": safe_boot_reason,
                    "safe_boot_ts": safe_boot_ts,
                    "blockers": list(real_blockers),
                },
            )
        )

        # --- check: runtime/signals.jsonl presence
        signals_path = Path(self.root_dir) / "runtime" / "signals.jsonl"
        signals_exists = bool(signals_path.exists())

        if not signals_exists and events_total == 0:
            findings.append(
                ReadinessFinding(
                    severity=ReadinessSeverity.WARNING,
                    code="READINESS_NO_SIGNALS_SOURCE",
                    message="No signals.jsonl found and replay returned zero events.",
                    metrics={"signals_exists": signals_exists, "events_total": events_total},
                )
            )
        else:
            findings.append(
                ReadinessFinding(
                    severity=ReadinessSeverity.OK,
                    code="READINESS_SIGNALS_SOURCE_PRESENT",
                    message="Signals source present or replay produced events.",
                    metrics={"signals_exists": signals_exists, "events_total": events_total},
                )
            )

        # --- check: timestamp quality + inversions
        ts_zero = 0
        inversions = 0
        prev_ts: float | None = None

        for e in events:
            ts = float(e.ts)
            if ts == 0.0:
                ts_zero += 1
            if prev_ts is not None and ts < prev_ts:
                inversions += 1
            prev_ts = ts

        ts_zero_ratio = (float(ts_zero) / float(events_total)) if events_total > 0 else 0.0
        inv_ratio = (float(inversions) / float(max(events_total - 1, 1))) if events_total > 1 else 0.0

        if ts_zero > 0:
            findings.append(
                ReadinessFinding(
                    severity=ReadinessSeverity.WARNING,
                    code="READINESS_TS_ZERO_PRESENT",
                    message="Some events have zero/unknown timestamp.",
                    metrics={"ts_zero": int(ts_zero), "events_total": events_total, "ts_zero_ratio": ts_zero_ratio},
                )
            )
        else:
            findings.append(
                ReadinessFinding(
                    severity=ReadinessSeverity.OK,
                    code="READINESS_TS_ZERO_NONE",
                    message="No zero/unknown timestamps detected.",
                    metrics={"ts_zero": int(ts_zero), "events_total": events_total, "ts_zero_ratio": ts_zero_ratio},
                )
            )

        # Inversions are not necessarily bad (multiple sources, coarse timestamps),
        # but we surface them as INFO/WARNING depending on ratio.
        if inv_ratio > 0.05:
            findings.append(
                ReadinessFinding(
                    severity=ReadinessSeverity.WARNING,
                    code="READINESS_TS_INVERSIONS_HIGH",
                    message="High ratio of timestamp inversions in sorted timeline.",
                    metrics={"inversions": int(inversions), "events_total": events_total, "inv_ratio": inv_ratio},
                )
            )
        elif inversions > 0:
            findings.append(
                ReadinessFinding(
                    severity=ReadinessSeverity.INFO,
                    code="READINESS_TS_INVERSIONS_PRESENT",
                    message="Timestamp inversions present (may be acceptable).",
                    metrics={"inversions": int(inversions), "events_total": events_total, "inv_ratio": inv_ratio},
                )
            )
        else:
            findings.append(
                ReadinessFinding(
                    severity=ReadinessSeverity.OK,
                    code="READINESS_TS_INVERSIONS_NONE",
                    message="No timestamp inversions detected.",
                    metrics={"inversions": int(inversions), "events_total": events_total, "inv_ratio": inv_ratio},
                )
            )

        # --- incidents distribution (fact only)
        levels = {}
        for i in (incidents or []):
            k = str(i.level.value)
            levels[k] = int(levels.get(k, 0)) + 1

        findings.append(
            ReadinessFinding(
                severity=ReadinessSeverity.OK if incidents_total == 0 else ReadinessSeverity.INFO,
                code="READINESS_INCIDENTS_SUMMARY",
                message="Incidents distribution (diagnostic only).",
                metrics={"incidents_total": incidents_total, "levels": dict(levels)},
            )
        )

        # --- checkpoints presence (stored inside replay.stats)
        cps_total = int((replay.stats or {}).get("checkpoints_total", 0))
        if cps_total >= 2:
            findings.append(
                ReadinessFinding(
                    severity=ReadinessSeverity.OK,
                    code="READINESS_CHECKPOINTS_PRESENT",
                    message="Replay checkpoints present.",
                    metrics={"checkpoints_total": cps_total},
                )
            )
        else:
            findings.append(
                ReadinessFinding(
                    severity=ReadinessSeverity.INFO,
                    code="READINESS_CHECKPOINTS_MISSING",
                    message="Replay checkpoints missing or incomplete.",
                    metrics={"checkpoints_total": cps_total},
                )
            )

        # --- guard rails diagnostics (read-only)
        guard_state_path = Path(self.root_dir) / "runtime" / "guard_rails_state.json"
        gr_attempts_24h = 0
        gr_symbols = set()

        if guard_state_path.exists():
            try:
                with guard_state_path.open("r", encoding="utf-8") as f:
                    gr_state = json.load(f) or {}
                attempts = gr_state.get("attempts") or []
                for a in attempts:
                    ts_ms = int(a.get("ts_ms", 0))
                    if ts_ms > 0:
                        gr_attempts_24h += 1
                        s = a.get("symbol")
                        if s:
                            gr_symbols.add(str(s))
                findings.append(
                    ReadinessFinding(
                        severity=ReadinessSeverity.OK,
                        code="READINESS_GUARD_RAILS_STATE_PRESENT",
                        message="Guard rails state present (diagnostic only).",
                        metrics={
                            "attempts_24h": gr_attempts_24h,
                            "symbols_seen": sorted(gr_symbols),
                        },
                    )
                )
            except Exception:
                findings.append(
                    ReadinessFinding(
                        severity=ReadinessSeverity.INFO,
                        code="READINESS_GUARD_RAILS_STATE_INVALID",
                        message="Guard rails state present but failed to parse.",
                        metrics={},
                    )
                )
        else:
            findings.append(
                ReadinessFinding(
                    severity=ReadinessSeverity.INFO,
                    code="READINESS_GUARD_RAILS_STATE_MISSING",
                    message="Guard rails state file not found (may be expected).",
                    metrics={},
                )
            )

        # --- schema presence (diagnostic only)
        schema_missing = 0
        for e in events:
            p = dict(e.payload or {})
            sch = p.get("_schema")
            if not isinstance(sch, dict) or "name" not in sch or "version" not in sch:
                schema_missing += 1

        schema_missing_ratio = (float(schema_missing) / float(events_total)) if events_total > 0 else 0.0

        if events_total > 0 and schema_missing > 0:
            findings.append(
                ReadinessFinding(
                    severity=ReadinessSeverity.INFO,
                    code="READINESS_SCHEMA_MISSING_IN_EVENTS",
                    message="Some events are missing _schema (expected for historical records).",
                    metrics={
                        "schema_missing": int(schema_missing),
                        "events_total": events_total,
                        "schema_missing_ratio": schema_missing_ratio,
                    },
                )
            )
        else:
            findings.append(
                ReadinessFinding(
                    severity=ReadinessSeverity.OK,
                    code="READINESS_SCHEMA_PRESENT_IN_EVENTS",
                    message="All events have _schema (or no events).",
                    metrics={
                        "schema_missing": int(schema_missing),
                        "events_total": events_total,
                        "schema_missing_ratio": schema_missing_ratio,
                    },
                )
            )

        # --- report metrics
        report_metrics: Dict[str, Any] = {
            "events_total": events_total,
            "incidents_total": incidents_total,
            "signals_exists": signals_exists,
            "ts_zero": int(ts_zero),
            "ts_zero_ratio": ts_zero_ratio,
            "ts_inversions": int(inversions),
            "ts_inversion_ratio": inv_ratio,
            "checkpoints_total": cps_total,
        }

        # --- human-readable summary (non-gate)
        primary_blocker = real_blockers[0] if real_blockers else ""
        report_metrics["summary"] = {
            "real_ready": not bool(real_blockers),
            "primary_blocker": primary_blocker,
            "blockers": list(real_blockers),
        }

        return ReadinessReport(findings=findings, metrics=report_metrics)

    @staticmethod
    def to_dict(report: ReadinessReport) -> Dict[str, Any]:
        return {
            "metrics": dict(report.metrics or {}),
            "findings": [
                {
                    "severity": str(f.severity.value),
                    "code": str(f.code),
                    "message": str(f.message),
                    "metrics": dict(f.metrics or {}),
                }
                for f in (report.findings or [])
            ],
        }
