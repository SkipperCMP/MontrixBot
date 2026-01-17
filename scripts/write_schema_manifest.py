from __future__ import annotations

import json
from pathlib import Path

from core.schema_ids import SchemaIds, SchemaVersions
from core.system_clock import SystemClock


def main() -> int:
    root_dir = Path(__file__).resolve().parents[1]
    runtime_dir = root_dir / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "_schema": {"name": SchemaIds.SCHEMA_MANIFEST, "version": SchemaVersions.V1},
        "ts_wall_ms": SystemClock.now_wall_ms(),
        "artifacts": {
            SchemaIds.SIGNALS_RECORD: {"version": SchemaVersions.V1},
            SchemaIds.CLOCK_SNAPSHOT: {"version": SchemaVersions.V1},
            SchemaIds.REPLAY_LAST: {"version": SchemaVersions.V1},
            SchemaIds.INCIDENTS_LAST: {"version": SchemaVersions.V1},
            SchemaIds.READINESS_LAST: {"version": SchemaVersions.V1},
            SchemaIds.POLICY_TRACE_EVENT: {"version": SchemaVersions.V1},
        },
    }

    out_path = runtime_dir / "schema_manifest.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[schema] -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
