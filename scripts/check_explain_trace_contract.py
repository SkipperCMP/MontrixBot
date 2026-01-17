# MontrixBot
# UI-only regression test: Explain Trace / Silence Explainability
# Ensures format_explain_panel():
#  - does not crash without runtime/events.jsonl
#  - tolerates bad lines in events.jsonl
#  - accepts python-dict single quotes
#  - produces expected trace statuses (NO_DECISION_YET / COOLDOWN_ACTIVE)

from __future__ import annotations

import os
import sys
import time
import tempfile
import shutil
from pathlib import Path


def _assert_contains(hay: str, needle: str) -> None:
    if needle not in hay:
        raise AssertionError(f"Expected to find {needle!r} in output, but it was missing.")


def _build_min_payload() -> dict:
    # Minimal payload matching our UI expectations
    return {
        "fsm": "TRADING_ACTIVE",
        "mode": "MANUAL_ONLY",
        "policy_hard_stop_active": False,
        "why_not": ["MODE_MANUAL_ONLY"],
        "gate_last": {
            "decision": "VETO",
            "reasons": ["MODE_MANUAL_ONLY"],
            "evidence": ["test:evidence"],
            "source": "test",
            "ts_utc": "2026-01-06T00:00:00+00:00",
        },
    }


def _run_case_no_events_file() -> None:
    from ui.explain_panel import format_explain_panel  # import inside case

    payload = _build_min_payload()
    out = format_explain_panel(payload)

    _assert_contains(out, "WHY NOT:")
    _assert_contains(out, "SIM:")
    _assert_contains(out, "DECISION TRACE:")
    _assert_contains(out, "status: NO_DECISION_YET")
    _assert_contains(out, "SIM is observing")


def _run_case_bad_lines_and_cooldown() -> None:
    from ui.explain_panel import format_explain_panel  # import inside case

    payload = _build_min_payload()

    Path("runtime").mkdir(parents=True, exist_ok=True)
    p = Path("runtime") / "events.jsonl"

    ts = time.time() - 5.0  # inside 30s cooldown

    # Include:
    #  - a broken line
    #  - a python-dict single-quote line (SIM_DECISION_JOURNAL)
    #  - a JSON line (SIGNAL) to exercise parser tolerance
    lines = [
        "{ this is not json }",
        (
            "{'type': 'SIM_DECISION_JOURNAL', 'ts': %s, "
            "'payload': {'recommended_action': 'BUY', 'confidence': 0.70, "
            "'signals': {'input_side': 'BUY'}, 'hypothesis': 'test'}}"
        )
        % ts,
        '{"type":"SIGNAL","ts":%s,"payload":{"side":"BUY"}}' % ts,
    ]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8", errors="strict")

    out = format_explain_panel(payload)

    _assert_contains(out, "SIM:")
    _assert_contains(out, "DECISION TRACE:")
    _assert_contains(out, "status: COOLDOWN_ACTIVE")
    _assert_contains(out, "cooldown_remaining_s:")


def main() -> int:
    print(">> Explain Trace Contract Test (UI-only)")

    old_cwd = os.getcwd()
    td = None

    try:
        # Use mkdtemp + manual cleanup: TemporaryDirectory cleanup can fail on Windows
        td = tempfile.mkdtemp(prefix="montrixbot_explain_test_")
        os.chdir(td)

        print(">> Case 1: no runtime/events.jsonl")
        _run_case_no_events_file()
        print("[OK] Case 1 OK")

        print(">> Case 2: bad lines + python-dict + cooldown")
        _run_case_bad_lines_and_cooldown()
        print("[OK] Case 2 OK")

        print("\nEXPLAIN TRACE CONTRACT CHECK PASSED")
        return 0

    except Exception as e:
        print("\nEXPLAIN TRACE CONTRACT CHECK FAILED")
        print(type(e).__name__ + ":", str(e))
        return 2

    finally:
        # Always leave temp dir before attempting removal
        try:
            os.chdir(old_cwd)
        except Exception:
            pass

        # Best-effort cleanup (never fail the test on Windows locks)
        if td:
            try:
                shutil.rmtree(td)
            except PermissionError:
                print(f"Temp cleanup skipped (locked): {td}")
            except Exception:
                # ignore any cleanup errors
                pass

if __name__ == "__main__":
    raise SystemExit(main())