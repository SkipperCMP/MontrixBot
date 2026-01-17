from __future__ import annotations

import json
from pathlib import Path

from tools.replay import ReplayConfig, ReplaySession, IncidentExtractor, ReadinessRunner
from core.schema_ids import SchemaIds, SchemaVersions


def main() -> int:
    # project root = parent of this scripts dir
    root_dir = Path(__file__).resolve().parents[1]
    cfg = ReplayConfig(root_dir=str(root_dir), include_signals=True, strict_json=False, max_events=None)

    res = ReplaySession(cfg).run()
    payload = res.to_dict()
    payload["_schema"] = {"name": SchemaIds.REPLAY_LAST, "version": SchemaVersions.V1}

    out_path = root_dir / "runtime" / "replay_last.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    extractor = IncidentExtractor()
    incidents = extractor.extract(res.events)
    incidents_payload = {
        "_schema": {"name": SchemaIds.INCIDENTS_LAST, "version": SchemaVersions.V1},
        "stats": {
            "incidents_total": int(len(incidents)),
            "levels": sorted(list({str(i.level.value) for i in incidents})),
        },
        "incidents": extractor.to_dict_list(incidents),
    }
    inc_path = root_dir / "runtime" / "incidents_last.json"
    inc_path.write_text(json.dumps(incidents_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    runner = ReadinessRunner(root_dir=str(root_dir))
    report = runner.run(res, incidents)
    readiness_payload = runner.to_dict(report)
    readiness_payload["_schema"] = {"name": SchemaIds.READINESS_LAST, "version": SchemaVersions.V1}

    rd_path = root_dir / "runtime" / "readiness_last.json"
    rd_path.write_text(json.dumps(readiness_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Console summary (diagnostic only)
    sev_counts = {}
    for f in readiness_payload.get("findings", []):
        sev = str(f.get("severity", "UNKNOWN"))
        sev_counts[sev] = int(sev_counts.get(sev, 0)) + 1

    print(f"[replay] events={payload['stats'].get('events_total')} -> {out_path}")
    print(f"[incidents] total={incidents_payload['stats']['incidents_total']} -> {inc_path}")
    print(f"[readiness] findings={len(readiness_payload.get('findings', []))} sev={sev_counts} -> {rd_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
