from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from core.system_clock import SystemClock
from core.schema_ids import SchemaIds, SchemaVersions


log = logging.getLogger(__name__)


def append_signal_record(rec: Dict[str, Any], *, root: Optional[Path] = None) -> None:
    """
    Core-owned persistence for signals history.

    IMPORTANT:
    - UI must NOT write runtime/signals.jsonl
    - UIAPI must NOT do file I/O
    """
    if not isinstance(rec, dict):
        return

    try:
        base = root if isinstance(root, Path) else Path(__file__).resolve().parents[1]
        path = base / "runtime" / "signals.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)

        # v1.9.A: ensure minimal time consistency for persisted records
        if "ts" not in rec:
            rec["ts"] = SystemClock.now_wall_ts()
        if "_clock" not in rec:
            rec["_clock"] = SystemClock.meta_dict()
        if "_schema" not in rec:
            rec["_schema"] = {"name": SchemaIds.SIGNALS_RECORD, "version": SchemaVersions.V1}

        line = json.dumps(rec, ensure_ascii=False)
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        # persistence must be best-effort, but never silent
        log.exception("SignalStore: failed to append signal record")
