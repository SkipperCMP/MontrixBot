from __future__ import annotations

import os
import time
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional

import logging

log = logging.getLogger(__name__)

_SCHEMES = [
    ("GENERIC", ("API_KEY", "API_SECRET")),
    ("BINANCE", ("BINANCE_API_KEY", "BINANCE_SECRET")),
]


@dataclass
class TechStopState:
    active: bool = False
    reasons: List[str] = None  # type: ignore
    fail_streak: int = 0
    ok_streak: int = 0
    total_enters: int = 0
    last_change_ts: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active": bool(self.active),
            "reasons": list(self.reasons or []),
            "fail_streak": int(self.fail_streak),
            "ok_streak": int(self.ok_streak),
            "total_enters": int(self.total_enters),
            "last_change_ts": float(self.last_change_ts or 0.0),
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "TechStopState":
        return TechStopState(
            active=bool(d.get("active", False)),
            reasons=list(d.get("reasons", []) or []),
            fail_streak=int(d.get("fail_streak", 0) or 0),
            ok_streak=int(d.get("ok_streak", 0) or 0),
            total_enters=int(d.get("total_enters", 0) or 0),
            last_change_ts=float(d.get("last_change_ts", 0.0) or 0.0),
        )


def _read_env(path: str) -> Dict[str, str]:
    data: Dict[str, str] = {}
    if not os.path.exists(path):
        return data
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                data[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        return {}
    return data


def _keys_present() -> bool:
    # Check OS env first, then .env in project root
    merged = dict(os.environ)
    merged.update(_read_env(".env"))

    for _name, (k1, k2) in _SCHEMES:
        v1 = str(merged.get(k1, "") or "").strip()
        v2 = str(merged.get(k2, "") or "").strip()
        if v1 and v2:
            return True
    return False


class TechStopGuard:
    """
    TECH STOP = only fact-based blocks.
    Current v1 trigger: missing API keys (100% fact).
    """
    def __init__(
        self,
        state_path: str = "runtime/tech_stop_state.json",
        confirm_required: int = 2,
    ) -> None:
        self._path = Path(state_path)
        self._confirm = int(confirm_required)

    def _load(self) -> TechStopState:
        if not self._path.exists():
            self._path.parent.mkdir(parents=True, exist_ok=True)
            st = TechStopState(active=False, reasons=[])
            self._path.write_text(json.dumps(st.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
            return st
        try:
            raw = self._path.read_text(encoding="utf-8").strip()
            return TechStopState.from_dict(json.loads(raw or "{}"))
        except Exception:
            st = TechStopState(active=False, reasons=[])
            self._path.write_text(json.dumps(st.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
            return st

    def _save(self, st: TechStopState) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(st.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def update(self, fsm) -> None:
        """
        Update FSM based on fact-based signals.
        Called from StatusService (UI refresh path) so it works even without ticks.
        """
        st = self._load()

        ok = _keys_present()
        now = time.time()

        if ok:
            st.ok_streak += 1
            st.fail_streak = 0
        else:
            st.fail_streak += 1
            st.ok_streak = 0

        # ENTER TECH STOP
        if st.fail_streak >= self._confirm:
            # TECH STOP dominates over any existing HARD_STOPPED (including manual)
            st.active = True
            st.reasons = ["API_KEYS_MISSING"]
            st.total_enters += 1
            st.last_change_ts = now
            self._save(st)

            try:
                fsm.tech_stop_enter(["API_KEYS_MISSING"])
            except Exception:
                pass

            log.error("TECH_STOP ENTER (dominant): API keys missing (confirmed)")
            return

        # EXIT TECH STOP (only if current FSM is tech stop)
        if st.active and ok and (st.ok_streak >= self._confirm):
            st.active = False
            st.reasons = []
            st.last_change_ts = now
            self._save(st)
            try:
                fsm.tech_stop_clear_if_active()
            except Exception:
                pass
            log.info("TECH_STOP EXIT: API keys present (confirmed)")
            return

        self._save(st)


_guard_singleton: Optional[TechStopGuard] = None


def get_tech_stop_guard() -> TechStopGuard:
    global _guard_singleton
    if _guard_singleton is None:
        _guard_singleton = TechStopGuard()
    return _guard_singleton
