from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any

from core.types_runtime import AutonomyMode


DEFAULT_STATE = {
    "mode": AutonomyMode.MANUAL_ONLY.value,
    "hard_stop_active": False,
}


@dataclass
class AutonomyPolicySnapshot:
    mode: str
    hard_stop_active: bool


class AutonomyPolicyStore:
    """
    Skeleton: source of truth for autonomy mode + hard stop flag.

    IMPORTANT:
      - no auto transitions
      - only explicit setters (later via CommandRouter)
    """

    def __init__(self, state_path: str = "runtime/autonomy_policy.json") -> None:
        self._path = Path(state_path)

    def _read(self) -> Dict[str, Any]:
        if not self._path.exists():
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(DEFAULT_STATE, ensure_ascii=False, indent=2), encoding="utf-8")
            return dict(DEFAULT_STATE)

        raw = self._path.read_text(encoding="utf-8").strip()
        if not raw:
            self._path.write_text(json.dumps(DEFAULT_STATE, ensure_ascii=False, indent=2), encoding="utf-8")
            return dict(DEFAULT_STATE)

        try:
            data = json.loads(raw)
        except Exception:
            data = dict(DEFAULT_STATE)
            self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        data.setdefault("mode", DEFAULT_STATE["mode"])
        data.setdefault("hard_stop_active", DEFAULT_STATE["hard_stop_active"])
        return data

    def _write(self, data: Dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def snapshot(self) -> AutonomyPolicySnapshot:
        data = self._read()
        return AutonomyPolicySnapshot(
            mode=str(data.get("mode", DEFAULT_STATE["mode"])),
            hard_stop_active=bool(data.get("hard_stop_active", False)),
        )

    def get_mode(self) -> AutonomyMode:
        snap = self.snapshot()
        try:
            return AutonomyMode(snap.mode)
        except Exception:
            return AutonomyMode.MANUAL_ONLY

    def is_hard_stop_active(self) -> bool:
        return self.snapshot().hard_stop_active

    def set_mode(self, new_mode: AutonomyMode, actor: str = "human", reason: str = "") -> None:
        data = self._read()
        data["mode"] = new_mode.value
        self._write(data)

    def set_hard_stop(self, active: bool, actor: str = "human", reason: str = "") -> None:
        data = self._read()
        data["hard_stop_active"] = bool(active)
        self._write(data)
