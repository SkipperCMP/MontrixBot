# MontrixBot
# UI-only proof test: UIAPI in READ-ONLY must NOT mutate runtime state files.
#
# IMPORTANT:
# - runtime/events.jsonl MAY change due to UI_READ_ONLY_BLOCK event emission (expected & allowed).
# - This test focuses on "state-like" runtime files (status/state/sim/trades/equity/signals), not event logs.

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path
from typing import Dict, Any, Tuple


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _snap(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    st = path.stat()
    return {
        "exists": True,
        "size": int(st.st_size),
        "mtime": float(st.st_mtime),
        "sha256": _sha256(path),
    }


def _diff(before: Dict[str, Any], after: Dict[str, Any]) -> str:
    if before.get("exists") != after.get("exists"):
        return f"exists: {before.get('exists')} -> {after.get('exists')}"
    if not before.get("exists"):
        return ""
    fields = ["size", "mtime", "sha256"]
    changed = []
    for k in fields:
        if before.get(k) != after.get(k):
            changed.append(f"{k}: {before.get(k)} -> {after.get(k)}")
    return "; ".join(changed)


def main() -> int:
    print(">> UI No Runtime Writes Proof Test (UI-only)")
    if not RUNTIME.exists():
        print("[SKIP] runtime/ directory not found")
        return 0

    # Runtime files that UI must not mutate in READ-ONLY mode.
    # (events.jsonl is intentionally excluded; it may log UI_READ_ONLY_BLOCK)
    targets = [
        RUNTIME / "status.json",
        RUNTIME / "state.json",
        RUNTIME / "sim_state.json",
        RUNTIME / "trades.jsonl",
        RUNTIME / "signals.jsonl",
        RUNTIME / "equity.jsonl",
        RUNTIME / "tpsl_config.json",
        RUNTIME / "tech_stop_state.json",
    ]

    before = {str(p): _snap(p) for p in targets}

    # Build UIAPI with dummy dependencies (guard should prevent any writes).
    from core.ui_api import UIAPI  # type: ignore

    dummy_state = object()
    dummy_executor = object()
    api = UIAPI(state=dummy_state, executor=dummy_executor)

    # Ensure read-only (should be default, but make it explicit).
    try:
        api.set_ui_read_only(True)
    except Exception:
        pass

    # Trigger a few "write-like" UI paths that must be blocked by _guard_write
    try:
        api.persist_trade_record({"ts": time.time(), "symbol": "TEST", "side": "BUY", "qty": 1, "source": "UI_TEST"})
        # Repeat quickly to exercise suppression path too
        api.persist_trade_record({"ts": time.time(), "symbol": "TEST", "side": "BUY", "qty": 1, "source": "UI_TEST"})
    except Exception as e:
        print("[FAIL] calling persist_trade_record raised:", repr(e))
        return 1

    try:
        api.persist_equity_point({"ts": time.time(), "equity": 123.45, "mode": "SIM"}, source="UI_TEST")
        api.persist_equity_point({"ts": time.time(), "equity": 123.45, "mode": "SIM"}, source="UI_TEST")
    except Exception as e:
        print("[FAIL] calling persist_equity_point raised:", repr(e))
        return 1

    # Optional calls if present (best-effort, never mandatory)
    # NOTE: persist_sim_state requires a mandatory 'snapshot' argument.
    for maybe_name in ["maybe_persist_runtime_state", "persist_sim_state", "reset_sim_state"]:
        fn = getattr(api, maybe_name, None)
        if callable(fn):
            try:
                if maybe_name == "persist_sim_state":
                    fn({"ts": time.time(), "source": "UI_TEST"})  # type: ignore
                else:
                    fn()  # type: ignore
            except Exception as e:
                print(f"[FAIL] calling {maybe_name} raised:", repr(e))
                return 1

    after = {str(p): _snap(p) for p in targets}

    # Compare snapshots
    changed = []
    for p in targets:
        k = str(p)
        d = _diff(before[k], after[k])
        if d:
            changed.append((k, d))

    if changed:
        print("[FAIL] UI mutated runtime state files (unexpected):")
        for path_s, d in changed:
            print("-", Path(path_s).relative_to(ROOT), "=>", d)
        return 1

    print("[OK] UI did not mutate runtime state files (events.jsonl excluded by design).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
