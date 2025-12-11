from __future__ import annotations

"""
scripts/test_runtime_state.py — быстрый sanity-check для core/runtime_state.py

Запуск:
    python -m scripts.test_runtime_state

Что делает:
    - читает текущее runtime-состояние через load_runtime_state();
    - добавляет в meta флаг last_runtime_state_test;
    - сохраняет состояние через save_runtime_state();
    - перечитывает и печатает укороченный результат.
"""

from typing import Any, Dict
import datetime as _dt
import json

from core.runtime_state import load_runtime_state, save_runtime_state


def _pretty(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        return repr(obj)


def main() -> None:
    print("=== STEP 1: load_runtime_state() ===")
    state1: Dict[str, Any] = load_runtime_state()
    print(_pretty({
        "positions_keys": list(state1.get("positions", {}).keys()),
        "meta": state1.get("meta", {}),
        "sim_present": bool(state1.get("sim")),
    }))

    # добавляем тестовый флаг в meta
    meta = dict(state1.get("meta", {}))
    meta["last_runtime_state_test"] = _dt.datetime.now().isoformat(timespec="seconds")
    state1["meta"] = meta

    print("\n=== STEP 2: save_runtime_state(updated_state) ===")
    save_runtime_state(state1)
    print("saved.")

    print("\n=== STEP 3: load_runtime_state() again ===")
    state2: Dict[str, Any] = load_runtime_state()
    print(_pretty({
        "positions_keys": list(state2.get("positions", {}).keys()),
        "meta": state2.get("meta", {}),
        "sim_present": bool(state2.get("sim")),
    }))

    print("\nOK: runtime_state round-trip completed.")


if __name__ == "__main__":
    main()
