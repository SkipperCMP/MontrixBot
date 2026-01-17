from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "runtime" / "autonomy_policy.json"
SAFE_FLAG = ROOT / "SAFE_MODE"
STATE_JSON = ROOT / "runtime" / "state.json"


def _run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    return int(p.returncode), out.strip()


def _clear_symbol_position(symbol: str) -> None:
    """Contract-test helper: ensure decision loop is not blocked by unrelated open positions."""
    sym = str(symbol or "").upper()
    if not sym:
        return
    try:
        if not STATE_JSON.exists():
            return
        data = json.loads(STATE_JSON.read_text(encoding="utf-8") or "{}")
        if not isinstance(data, dict):
            return
        pos = data.get("positions")
        if not isinstance(pos, dict):
            return
        if sym in pos:
            pos.pop(sym, None)
            data["positions"] = pos
            STATE_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        return


def main() -> int:
    # Preserve original policy
    orig = None
    try:
        if POLICY.exists():
            orig = POLICY.read_text(encoding="utf-8")
    except Exception:
        orig = None

    try:
        # Force AUTO_ALLOWED for this test
        POLICY.parent.mkdir(parents=True, exist_ok=True)
        POLICY.write_text(
            json.dumps({"mode": "AUTO_ALLOWED", "hard_stop_active": False}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Case A: REAL intent should request confirm token, never execute
        # Use a dedicated symbol and ensure no open position blocks intent creation.
        symbol = "AUTOTESTUSDT"
        _clear_symbol_position(symbol)

        code, out = _run(
            [
                sys.executable,
                "-m",
                "scripts.autonomy_decision_loop",
                "--mode",
                "REAL",
                "--signal",
                "BUY",
                "--symbol",
                symbol,
            ]
        )
        if code != 2:
            print("FAIL: expected exit=2 for REAL confirm required")
            print(out)
            return 1

        try:
            j = json.loads(out.splitlines()[-1])
        except Exception:
            print("FAIL: output is not json")
            print(out)
            return 1

        if j.get("status") != "CONFIRM_REQUIRED":
            print("FAIL: expected status=CONFIRM_REQUIRED")
            print(out)
            return 1

        if not j.get("confirm_token"):
            print("FAIL: confirm_token missing")
            print(out)
            return 1

        # Case B: SAFE hard-lock forces HOLD (no confirm)
        try:
            SAFE_FLAG.write_text("SAFE", encoding="utf-8")
        except Exception:
            pass

        code2, out2 = _run(
            [
                sys.executable,
                "-m",
                "scripts.autonomy_decision_loop",
                "--mode",
                "REAL",
                "--signal",
                "BUY",
                "--symbol",
                symbol,
            ]
        )
        if code2 != 0:
            print("FAIL: expected exit=0 when SAFE blocks entry (HOLD)")
            print(out2)
            return 1

        try:
            j2 = json.loads(out2.splitlines()[-1])
        except Exception:
            print("FAIL: output2 is not json")
            print(out2)
            return 1

        if j2.get("status") != "HOLD":
            print("FAIL: expected status=HOLD under SAFE_HARD_LOCK")
            print(out2)
            return 1

        print("[OK] Autonomy decision contract passed (REAL intents-only, SAFE priority).")
        return 0

    finally:
        # Restore
        try:
            if SAFE_FLAG.exists():
                SAFE_FLAG.unlink()
        except Exception:
            pass

        try:
            if orig is None:
                if POLICY.exists():
                    POLICY.unlink()
            else:
                POLICY.write_text(orig, encoding="utf-8")
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
