import json
import sys
import ast
from datetime import datetime, timezone
from pathlib import Path

RUNTIME = Path("runtime")
STATUS_FILE = RUNTIME / "status.json"
FSM_FILE = RUNTIME / "trading_fsm.json"
POLICY_FILE = RUNTIME / "autonomy_policy.json"
TECH_STOP_FILE = RUNTIME / "tech_stop_state.json"
EVENTS_FILE = Path("runtime/events.jsonl")  # canonical
LEGACY_EVENTS_FILE = Path("runtime/logs/events.jsonl")  # backward-compat


def _read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def _uniq(seq):
    out = []
    for x in seq:
        if x not in out:
            out.append(x)
    return out


def build_status_fallback():
    # Preserve existing status.json fields that are not derivable from runtime/*.json
    existing = {}
    try:
        if STATUS_FILE.exists():
            existing = _read_json(STATUS_FILE) or {}
    except Exception:
        existing = {}

    if not FSM_FILE.exists():
        raise FileNotFoundError(f"{FSM_FILE} not found")
    if not POLICY_FILE.exists():
        raise FileNotFoundError(f"{POLICY_FILE} not found")

    fsm = _read_json(FSM_FILE)
    policy = _read_json(POLICY_FILE)
    tech = _read_json(TECH_STOP_FILE) if TECH_STOP_FILE.exists() else {}

    state = fsm.get("state", "unavailable")
    pause_reasons = fsm.get("pause_reasons", []) or []

    tech_active = bool(tech.get("active", False))
    tech_reasons = tech.get("reasons", []) or []

    # Canonical why_not (no mixed raw strings like "tech stop" or "API_KEYS_MISSING")
    why_not = []

    def _add(x: str):
        x = str(x).strip()
        if x and x not in why_not:
            why_not.append(x)

    # Manual stop from policy is a fact
    if bool(policy.get("hard_stop_active", False)):
        _add("MANUAL_STOP")

    # MODE_MANUAL_ONLY is a fact-based block reason (Explainability 2.0, contract-safe)
    try:
        m = str(policy.get("mode", "") or "").upper().strip()
        if m in ("MANUAL_ONLY", "MANUAL"):
            _add("MODE_MANUAL_ONLY")
    except Exception:
        pass

    # Pause reasons from FSM can contain raw tokens — normalize them
    pr = [str(x).strip() for x in (pause_reasons or []) if str(x).strip()]
    pr_low = [s.lower() for s in pr]

    if "manual stop" in pr_low:
        _add("MANUAL_STOP")

    # TECH STOP as a fact: prefer tech_stop_state.json if active
    if tech_active:
        _add("TECH_STOP_ACTIVE")
        for r in tech_reasons:
            r = str(r).strip()
            if not r:
                continue
            if r.startswith("TECH_STOP:"):
                _add(r)
            else:
                _add(f"TECH_STOP:{r}")
    else:
        # If tech_stop_state.json is absent but FSM pause reasons mention tech stop
        if "tech stop" in pr_low:
            _add("TECH_STOP_ACTIVE")
            detail = ""
            for s in pr:
                if s.lower() == "tech stop":
                    continue
                detail = s.upper()
                break
            if detail:
                if detail.startswith("TECH_STOP:"):
                    detail = detail.split(":", 1)[1]
                _add(f"TECH_STOP:{detail}")

    out = {
        "fsm": state,
        "mode": policy.get("mode", "unavailable"),
        "policy_hard_stop_active": bool(policy.get("hard_stop_active", False)),
        "why_not": _uniq([str(x) for x in why_not]),
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "source": "runtime/status.json",
    }

    # Preserve gate explainability if present in existing status.json
    try:
        if isinstance(existing, dict):
            if "gate" in existing:
                out["gate"] = existing.get("gate")
            if "gate_last" in existing:
                out["gate_last"] = existing.get("gate_last")
    except Exception:
        pass

    return out


def check_status_snapshot(s: dict):
    print(">> Checking status snapshot")

    for key in ("fsm", "mode", "why_not"):
        if key not in s:
            print(f"[FAIL] Missing key: {key}")
            return False

    if s["fsm"] in (None, "", "unavailable"):
        print(f"[FAIL] Invalid FSM value: {s['fsm']}")
        return False

    if not isinstance(s["why_not"], list):
        print("[FAIL] why_not is not a list")
        return False

    # важная проверка: reasons не должны быть dict/сложными объектами
    for i, r in enumerate(s["why_not"]):
        if not isinstance(r, str):
            print(f"[FAIL] why_not[{i}] is not str: {r!r}")
            return False

    print("[OK] status snapshot OK")
    return True


def check_events():
    candidates = [EVENTS_FILE, LEGACY_EVENTS_FILE]
    path = None
    for p in candidates:
        if p.exists():
            path = p
            break

    if path is None:
        print("[WARN] events.jsonl not found (skipped)")
        return True

    print(f">> Checking events.jsonl ({path.as_posix()})")

    bad = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except Exception:
            try:
                # fallback for python-style single quotes
                e = ast.literal_eval(line)
                if not isinstance(e, dict):
                    raise ValueError("event is not a dict")
            except Exception as ex:
                # Tolerant mode: events.jsonl is an append-only log and may contain
                # legacy/corrupt lines. We WARN and skip, but do not fail the contract.
                print("[WARN] Skipping unparsable event line:")
                print(line)
                print(f"   error: {ex!r}")
                continue

        if e.get("type") == "ORDER_BLOCKED":
            reasons = e.get("why_not", [])
            for r in reasons:
                if isinstance(r, dict):
                    print(f"[FAIL] Dict reason found in event (should be str): {r}")
                    bad = True

    if bad:
        return False

    print("[OK] events.jsonl OK")
    return True


if __name__ == "__main__":
    ok = True

    # Always build canonical snapshot from runtime/*.json and overwrite runtime/status.json
    print(">> Building canonical runtime/status.json (from runtime/*.json)")
    status = build_status_fallback()

    try:
        RUNTIME.mkdir(parents=True, exist_ok=True)
        STATUS_FILE.write_text(
            json.dumps(status, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("[OK] Wrote runtime/status.json (canonical)")
    except Exception as e:
        print(f"[WARN] Failed to write runtime/status.json: {e!r}")

    print("--- snapshot ---")
    print(json.dumps(status, ensure_ascii=False, indent=2))

    ok &= check_status_snapshot(status)
    ok &= check_events()

    if not ok:
        print("\n[FAIL] CONTRACT CHECK FAILED")
        sys.exit(1)

    print("\n[OK] CONTRACT CHECK PASSED")
