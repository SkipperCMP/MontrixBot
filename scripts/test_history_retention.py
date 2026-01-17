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
    # Note: health_log retention is forbidden by POLICY-01 (see core/history_retention.py).
    # This test validates:
    #  - trades_jsonl is capped (max_lines from runtime/settings.json; expected default cap 5000)
    #  - health_log is NOT capped by retention (no shrink should occur)

    trades_path = "runtime/trades.jsonl"
    health_path = "runtime/health.log"

    # Seed data
    _append_lines(trades_path, 6200, "trade")
    _append_lines(health_path, 2600, "health")

    before_trades = _count_lines(trades_path)
    before_health = _count_lines(health_path)

    # Apply retention policies
    apply_retention_for_key(trades_path, "trades_jsonl")
    apply_retention_for_key(health_path, "health_log")

    after_trades = _count_lines(trades_path)
    after_health = _count_lines(health_path)

    print(f"trades.jsonl: before={before_trades} after={after_trades}")
    print(f"health.log: before={before_health} after={after_health}")

    if after_trades > before_trades:
        raise SystemExit("FAIL: trades lines increased")
    if after_health > before_health:
        raise SystemExit("FAIL: health lines increased")

    # trades should be capped
    if after_trades > 5000:
        raise SystemExit("FAIL: trades retention did not cap at 5000 lines")

    # health should NOT be capped (POLICY-01)
    if after_health < before_health:
        raise SystemExit("FAIL: health retention unexpectedly shrank health.log (POLICY-01 forbids it)")

    print("OK: retention behavior matches POLICY-01 (trades capped; health not capped)")


if __name__ == "__main__":
    main()
