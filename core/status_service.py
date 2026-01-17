from __future__ import annotations

from typing import Optional
from datetime import datetime, timezone

from core.types_runtime import StatusPayload, TradingState
from core.autonomy_policy import AutonomyPolicyStore
from core.trading_state_machine import TradingStateMachine


class ReadOnlyPositionProvider:
    """
    Skeleton interface.
    Позже адаптируем к STEP 1.x read-only источнику позиций/PnL.
    """

    def get_open_position_view(self) -> Optional[dict]:
        return None


class StatusService:
    """
    Builds canonical /status payload (no side effects).
    """

    def __init__(
        self,
        policy_store: AutonomyPolicyStore,
        fsm: TradingStateMachine,
        position_provider: Optional[ReadOnlyPositionProvider] = None,
    ) -> None:
        self._policy = policy_store
        self._fsm = fsm
        self._pos = position_provider or ReadOnlyPositionProvider()

    def build_status(self) -> StatusPayload:
        mode = self._policy.get_mode().value
        ts_utc = datetime.now(timezone.utc).isoformat()

        # TECH STOP (fact-based): core-owned guard updates FSM if needed
        try:
            from core.tech_stop_guard import get_tech_stop_guard
            get_tech_stop_guard().update(self._fsm)
        except Exception:
            # guard must never break status surface
            pass

        # FSM state must be resilient (UI should not show "unavailable" if file exists)
        state = None
        try:
            state = self._fsm.get_state().value
        except Exception:
            state = None

        # Fallback: read runtime/trading_fsm.json directly
        if not state:
            try:
                import json
                from pathlib import Path
                p = Path("runtime/trading_fsm.json")
                if p.exists():
                    raw = json.loads(p.read_text(encoding="utf-8") or "{}")
                    state = raw.get("state")
            except Exception:
                state = None

        state = state or TradingState.UNKNOWN.value

        # v2.0.7 — Single Source of why_not:
        from core.trade_permission import can_open_new_position_basic

        perm = can_open_new_position_basic(self._policy, self._fsm)

        is_trading = (state == TradingState.TRADING_ACTIVE.value)

        # Explainability 2.0 (contract-safe): why_not stays list[str]
        why_not = [str(x) for x in (perm.reasons or [])] if (not perm.allow) else []

        # MODE_MANUAL_ONLY is a fact-based block reason for operator clarity
        try:
            m = str(mode or "").upper()
            if m in ("MANUAL_ONLY", "MANUAL"):
                if "MODE_MANUAL_ONLY" not in why_not:
                    why_not.append("MODE_MANUAL_ONLY")
        except Exception:
            pass

        # Keep UI compact (but do not change contract type)
        why_not = why_not[:5]

        open_pos = self._pos.get_open_position_view()

        # v2.2.0 — GateEngine dry verdict (read-only)
        gate = None
        try:
            from core.gate_engine import GateEngine, GateContext

            import time

            gate = GateEngine().evaluate(
                GateContext(
                    mode=mode,
                    state=state,
                    is_trading=is_trading,
                    open_position=open_pos,
                    policy_hard_stop_active=self._policy.is_hard_stop_active(),
                    fsm_pause_reasons=(self._fsm.get_pause_reasons() if hasattr(self._fsm, "get_pause_reasons") else []),
                    why_not=why_not,
                    status_ts=int(time.time()),
                    policy_file_ref="runtime/autonomy_policy.json",
                    fsm_file_ref="runtime/trading_fsm.json",
                )
            )
        except Exception:
            gate = None

        # Emit runtime/status.json so scripts do NOT need fallback(runtime/*.json)
        try:
            import json
            import time
            from pathlib import Path

            # Status → Event bridging (best-effort, read-only)
            prev = None
            try:
                p_prev = Path("runtime/status.json")
                if p_prev.exists():
                    prev = json.loads(p_prev.read_text(encoding="utf-8") or "{}")
            except Exception:
                prev = None

            Path("runtime").mkdir(parents=True, exist_ok=True)

            # GateDecision is a dataclass -> convert to JSON-safe dict for runtime/status.json
            gate_dict = None
            try:
                if gate is not None:
                    gate_dict = {
                        "decision": str(getattr(gate, "decision", "")),
                        "reasons": [str(x) for x in (getattr(gate, "reasons", []) or [])],
                        "evidence": [str(x) for x in (getattr(gate, "evidence", []) or [])],
                    }
            except Exception:
                gate_dict = None

            payload = {
                "fsm": state,
                "mode": mode,
                "policy_hard_stop_active": bool(self._policy.is_hard_stop_active()),
                "why_not": [str(x) for x in (why_not or [])],
                "gate": (gate_dict or None),
                "ts": int(time.time()),
                "ts_utc": ts_utc,
                "source": "status_service",
            }

            # Gate Explainability Cache (SIM-only, Read-Only)
            try:
                if isinstance(gate_dict, dict) and gate_dict.get("decision"):
                    payload["gate_last"] = {
                        "decision": str(gate_dict.get("decision")),
                        "reasons": [str(x) for x in (gate_dict.get("reasons") or [])],
                        "evidence": [str(x) for x in (gate_dict.get("evidence") or [])],
                        "source": "gate_engine",
                        "ts_utc": ts_utc,
                    }
            except Exception:
                pass
            Path("runtime/status.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            # Emit STATUS_CHANGED event if something important changed.
            try:
                from core.event_bus import get_event_bus, make_event, new_cid
                changed = []
                if isinstance(prev, dict):
                    for k in ("fsm", "mode", "policy_hard_stop_active", "why_not"):
                        if prev.get(k) != payload.get(k):
                            changed.append(k)
                    # gate decision change (compact)
                    try:
                        prev_g = (prev.get("gate") or {}) if isinstance(prev.get("gate"), dict) else {}
                        now_g = (payload.get("gate") or {}) if isinstance(payload.get("gate"), dict) else {}
                        if str(prev_g.get("decision")) != str(now_g.get("decision")):
                            changed.append("gate.decision")
                    except Exception:
                        pass
                else:
                    # first write -> still useful marker
                    changed = ["status.init"]

                if changed:
                    bus = get_event_bus()
                    cid = new_cid()
                    bus.publish(
                        make_event(
                            "STATUS_CHANGED",
                            {
                                "fields_changed": changed,
                                "status_ref": "runtime/status.json",
                                "fsm": state,
                                "mode": mode,
                                "ts_utc": ts_utc,
                            },
                            actor="system",
                            cid=cid,
                        )
                    )
            except Exception:
                pass
        except Exception:
            # status surface must never break runtime
            pass

        return StatusPayload(
            is_trading=is_trading,
            state=state,
            mode=mode,
            why_not=why_not,
            open_position=open_pos,
            gate=gate,
            ts_utc=ts_utc,
        )
