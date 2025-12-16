from __future__ import annotations

import os
import time

from core.history_retention import apply_retention_for_key


def _count_lines(path: str) -> int:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def _append_lines(path: str, n: int, prefix: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for i in range(n):
            f.write(f"{prefix} line={i} ts={time.time()}\n")


def main() -> None:
    trades_path = "runtime/trades.jsonl"
    health_path = "runtime/health.log"

    # 1) Create big files
    _append_lines(trades_path, 6200, "TRADES_FAKE")
    _append_lines(health_path, 2600, "HEALTH_FAKE")

    before_trades = _count_lines(trades_path)
    before_health = _count_lines(health_path)

    # 2) Apply retention (reads runtime/settings.json -> history_retention)
    apply_retention_for_key(trades_path, "trades_jsonl")
    apply_retention_for_key(health_path, "health_log")

    after_trades = _count_lines(trades_path)
    after_health = _count_lines(health_path)

    print("=== HISTORY RETENTION TEST ===")
    print(f"trades.jsonl: before={before_trades} after={after_trades}")
    print(f"health.log  : before={before_health} after={after_health}")

    # 3) Simple asserts (best-effort; won't crash if policy missing)
    # Expected (with our settings): trades<=5000, health<=2000
    if after_trades > before_trades:
        raise SystemExit("FAIL: trades lines increased")
    if after_health > before_health:
        raise SystemExit("FAIL: health lines increased")

    # If policies are set, enforce expected caps:
    if after_trades > 5000:
        raise SystemExit("FAIL: trades retention did not cap at 5000 lines")
    if after_health > 2000:
        raise SystemExit("FAIL: health retention did not cap at 2000 lines")

    print("OK: retention caps applied")


if __name__ == "__main__":
    main()
