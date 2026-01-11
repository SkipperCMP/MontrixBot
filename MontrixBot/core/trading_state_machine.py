from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List

from core.types_runtime import TradingState


DEFAULT_TRADE_STATE = {
    "state": TradingState.TRADING_ACTIVE.value,
    "pause_reasons": [],
}


@dataclass
class TradingStateSnapshot:
    state: str
    pause_reasons: List[str]


def _normalize_reasons(reasons: List[str]) -> List[str]:
    cleaned = [str(r).strip() for r in (reasons or []) if str(r).strip()]
    return cleaned[:3]


class TradingStateMachine:
    """
    Canonical FSM owner (skeleton).

    Only manual transitions in this commit.
    No periodic Gate, no auto pause/resume here yet.
    """

    def __init__(self, state_path: str = "runtime/trading_fsm.json") -> None:
        self._path = Path(state_path)

    def _read(self) -> Dict[str, Any]:
        if not self._path.exists():
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(DEFAULT_TRADE_STATE, ensure_ascii=False, indent=2), encoding="utf-8")
            return dict(DEFAULT_TRADE_STATE)

        raw = self._path.read_text(encoding="utf-8").strip()
        if not raw:
            self._path.write_text(json.dumps(DEFAULT_TRADE_STATE, ensure_ascii=False, indent=2), encoding="utf-8")
            return dict(DEFAULT_TRADE_STATE)

        try:
            data = json.loads(raw)
        except Exception:
            data = dict(DEFAULT_TRADE_STATE)
            self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        data.setdefault("state", DEFAULT_TRADE_STATE["state"])
        data.setdefault("pause_reasons", [])
        return data

    def _write(self, data: Dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def snapshot(self) -> TradingStateSnapshot:
        data = self._read()
        return TradingStateSnapshot(
            state=str(data.get("state", DEFAULT_TRADE_STATE["state"])),
            pause_reasons=list(data.get("pause_reasons", [])),
        )

    def get_state(self) -> TradingState:
        snap = self.snapshot()
        try:
            return TradingState(snap.state)
        except Exception:
            return TradingState.TRADING_ACTIVE

    def get_pause_reasons(self) -> List[str]:
        return _normalize_reasons(self.snapshot().pause_reasons)

    # Manual transitions (skeleton)
    def manual_pause(self, reasons: List[str], actor: str = "human") -> None:
        data = self._read()
        data["state"] = TradingState.AUTO_PAUSED.value
        data["pause_reasons"] = _normalize_reasons(reasons)
        self._write(data)

    def manual_stop(self, reasons: List[str], actor: str = "human") -> None:
        data = self._read()
        data["state"] = TradingState.HARD_STOPPED.value
        normalized = _normalize_reasons(["manual stop"] + (reasons or []))
        data["pause_reasons"] = normalized
        self._write(data)

    # --- TECH STOP (core-owned, fact-based) ---
    def tech_stop_enter(self, reasons: List[str]) -> None:
        data = self._read()
        data["state"] = TradingState.HARD_STOPPED.value
        normalized = _normalize_reasons(["tech stop"] + (reasons or []))
        data["pause_reasons"] = normalized
        self._write(data)

    def tech_stop_clear_if_active(self) -> None:
        snap = self.snapshot()
        rs = _normalize_reasons(snap.pause_reasons)
        if (snap.state == TradingState.HARD_STOPPED.value) and ("tech stop" in rs):
            data = self._read()
            data["state"] = TradingState.TRADING_ACTIVE.value
            data["pause_reasons"] = []
            self._write(data)

    def is_tech_stop_active(self) -> bool:
        snap = self.snapshot()
        rs = _normalize_reasons(snap.pause_reasons)
        return (snap.state == TradingState.HARD_STOPPED.value) and ("tech stop" in rs)

    def manual_resume_to_active(self, actor: str = "human") -> None:
        # Gate check подключим позже строго по STEP_2_0_FSM_INTEGRATION.md
        data = self._read()
        data["state"] = TradingState.TRADING_ACTIVE.value
        data["pause_reasons"] = []
        self._write(data)

