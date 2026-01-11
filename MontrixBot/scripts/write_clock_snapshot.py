from __future__ import annotations

import json
from pathlib import Path

from core.system_clock import SystemClock
from core.schema_ids import SchemaIds, SchemaVersions


def main() -> int:
    root_dir = Path(__file__).resolve().parents[1]
    runtime_dir = root_dir / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    meta = SystemClock.meta_dict()
    payload = {
        "_schema": {"name": SchemaIds.CLOCK_SNAPSHOT, "version": SchemaVersions.V1},
        "ts_wall_ms": SystemClock.now_wall_ms(),
        "ts_exchange_ms": SystemClock.now_exchange_ms(),
        "meta": meta,
    }

    out_path = runtime_dir / "clock_snapshot.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[clock] -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
