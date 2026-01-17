import json
from datetime import datetime, timezone
from pathlib import Path

# UI-only: RU Reason Map (display only)
try:
    from ui.reasons_map import human_reason  # type: ignore
except Exception:
    def human_reason(x):  # fallback, контракт сохраняется
        return x


STALE_STATUS_AGE_SEC = 30

def _read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {}

def _uniq(xs):
    out = []
    for x in xs:
        if x not in out:
            out.append(x)
    return out

def _format_why_not(why):
    # UI-only mirror: человекочитаемое отображение причин (RU),
    # без изменения контрактных кодов.
    if not why:
        return ""
    why = [str(x).strip() for x in why if str(x).strip()]
    why = _uniq(why)
    return " | ".join(str(human_reason(x)) for x in why)

def main():
    status_path = Path("runtime/status.json")
    policy_path = Path("runtime/autonomy_policy.json")
    fsm_path = Path("runtime/trading_fsm.json")
    tech_path = Path("runtime/tech_stop_state.json")

    if status_path.exists():
        s = _read_json(status_path)
        src = "runtime/status.json"
    else:
        # fallback like your contract checker does
        policy = _read_json(policy_path) if policy_path.exists() else {}
        fsm = _read_json(fsm_path) if fsm_path.exists() else {}
        tech = _read_json(tech_path) if tech_path.exists() else {}

        # we will self-emit runtime/status.json after building the snapshot

        why = []
        hard = bool(policy.get("hard_stop_active", False))
        if hard:
            why.append("MANUAL_STOP")

        state = str(fsm.get("state") or "UNKNOWN")
        if state == "HARD_STOPPED":
            reasons = fsm.get("pause_reasons") or []
            reasons = [str(x).strip() for x in reasons if str(x).strip()]
            if any(x.lower() == "tech stop" for x in reasons):
                why.append("TECH_STOP_ACTIVE")

        if bool(tech.get("active", False)):
            why.append("TECH_STOP_ACTIVE")

            # Prefer canonical list: tech["reasons"] (as in contract checker)
            reasons = tech.get("reasons", []) or []
            reasons = [str(x).strip() for x in reasons if str(x).strip()]
            for r in reasons:
                if r.startswith("TECH_STOP:"):
                    why.append(r)
                else:
                    why.append(f"TECH_STOP:{r}")

            # Back-compat: if older file uses reason_code
            code = str(tech.get("reason_code") or "").strip().upper()
            if code:
                why.append(f"TECH_STOP:{code}")

        s = {
            "fsm": state,
            "mode": str(policy.get("mode") or "unavailable"),
            "policy_hard_stop_active": hard,
            "why_not": _uniq([str(x) for x in why]),
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "source": "runtime/status.json",
        }
        src = s["source"]

        # Best-effort: emit runtime/status.json, but only claim it if write succeeds
        try:
            Path("runtime").mkdir(parents=True, exist_ok=True)
            status_path.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
            src = "runtime/status.json"
        except Exception:
            pass

    fsm = str(s.get("fsm") or "")
    mode = str(s.get("mode") or "")
    why = s.get("why_not") or []
    why = [str(x) for x in why]

    print(f"— source: {src} —")
    print("snapshot:", json.dumps(s, ensure_ascii=False, indent=2))
    print()
    print("UI status line:")
    line = f"FSM={fsm} | MODE={mode}"

    # freshness (read-only)
    age_sec = None
    ts = s.get("ts_utc")
    if ts:
        try:
            ts_dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            age_sec = int((datetime.now(timezone.utc) - ts_dt).total_seconds())
        except Exception:
            age_sec = None

    if age_sec is not None and age_sec >= 0:
        if age_sec >= STALE_STATUS_AGE_SEC:
            line += f" | age={age_sec}s | STALE"
        else:
            line += f" | age={age_sec}s"
    else:
        line += " | age=unknown"

    reason = _format_why_not(why)
    if reason:
        line += f" | reason={reason}"
    print(line)

if __name__ == "__main__":
    main()
