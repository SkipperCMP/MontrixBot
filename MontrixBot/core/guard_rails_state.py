import json
import os
import time
from typing import Dict, List

from core.schema_ids import SchemaIds


class GuardRailsState:
    def __init__(self, attempts: List[dict], last_by_symbol: Dict[str, int]):
        self.attempts = attempts
        self.last_by_symbol = last_by_symbol

    @classmethod
    def empty(cls) -> "GuardRailsState":
        return cls(attempts=[], last_by_symbol={})

    def record_attempt(self, *, ts_ms: int, symbol: str) -> None:
        self.attempts.append({"ts_ms": int(ts_ms), "symbol": symbol})
        self.last_by_symbol[symbol] = int(ts_ms)

    def trim(self, *, max_age_ms: int) -> None:
        cutoff = int(time.time() * 1000) - int(max_age_ms)
        self.attempts = [a for a in self.attempts if int(a.get("ts_ms", 0)) >= cutoff]


def load_guard_rails_state(path: str) -> GuardRailsState:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return GuardRailsState.empty()

    return GuardRailsState(
        attempts=data.get("attempts", []),
        last_by_symbol=data.get("last_by_symbol", {}),
    )


def save_guard_rails_state_atomic(path: str, state: GuardRailsState) -> None:
    tmp = path + ".tmp"

    schema = SchemaIds.RUNTIME_GUARD_RAILS_STATE
    payload = {
        "_schema": {"name": schema[0], "version": schema[1]},
        "attempts": state.attempts,
        "last_by_symbol": state.last_by_symbol,
    }

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
