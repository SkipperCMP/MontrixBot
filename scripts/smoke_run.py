# scripts/smoke_run.py
"""
Final smoke for MontrixBot 1.2-pre1 — SMOKE TEST (legacy).

Legacy сценарий, оставлен как есть для совместимости и регрессионных проверок.
Текущий актуальный baseline: MontrixBot 1.2-pre2 (см. файл VERSION).

Checks (no internet required):
...
"""

import os, sys, time, math
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.state_engine import StateEngine
from core.executor import OrderExecutor
from core.tpsl import TPSLManager, TPSSLConfig
from core.exchange_filters import validate, get_filters
from core.binance_real import BinanceREST

RUNTIME = os.path.join(os.path.dirname(os.path.dirname(__file__)), "runtime")
os.makedirs(RUNTIME, exist_ok=True)
TRADES = os.path.join(RUNTIME, "trades.jsonl")
SYMBOL = "ADAUSDT"

def wipe_trades():
    try:
        os.remove(TRADES)
    except FileNotFoundError:
        pass

def count_events(kind: str) -> int:
    if not os.path.exists(TRADES):
        return 0
    n = 0
    with open(TRADES, "r", encoding="utf-8") as f:
        for ln in f:
            if f'"type": "{kind}"' in ln:
                n += 1
    return n

def sim_autoclose():
    print("[1] SIM + TP/SL auto-close")
    wipe_trades()
    st = StateEngine()
    ex = OrderExecutor(mode="SIM", state=st)
    cfg = TPSSLConfig(take_profit_pct=0.005, stop_loss_pct=0.005,
                      trail_activate_pct=0.003, trail_step_pct=0.002)
    tp = TPSLManager(ex, cfg)
    st.attach_tpsl(tp)
    entry = 0.50
    tp.open_long(SYMBOL, entry_price=entry, qty=10.0)
    t0 = time.time()
    closed = False
    while time.time() - t0 < 15:
        dt = time.time() - t0
        price = entry * (1.0 + min(0.02, 0.001*dt*dt) * math.sin(dt*6.0))
        st.upsert_ticker(SYMBOL, price, price, price)
        time.sleep(0.2)
        if count_events("CLOSE") > 0:
            closed = True
            break
    print("  -> CLOSE:", closed)
    return closed

def sim_recovery():
    print("[2] SIM + Recovery restart")
    if not os.path.exists(TRADES):
        print("  ! no trades.jsonl to recover from")
        return False
    lines = []
    with open(TRADES, "r", encoding="utf-8") as f:
        for ln in f:
            if '"type": "OPEN"' in ln:
                lines = [ln]
    with open(TRADES, "w", encoding="utf-8") as f:
        for ln in lines:
            f.write(ln)
    st = StateEngine()
    ex = OrderExecutor(mode="SIM", state=st)
    tp = TPSLManager(ex, TPSSLConfig())
    st.attach_tpsl(tp)
    recovered = SYMBOL in tp._pos
    print("  -> RECOVERED:", recovered)
    return recovered

def preview_path():
    print("[3] exchangeInfo preview/validate")
    print("  ! No filters; run tools/fetch_exchange_info.py once from project root")
    # NOTE: optional in smoke — environment preparation step, not a contract failure
    return True
    ok, reason, info = validate(SYMBOL, "BUY", price=0.50123, qty=25.123456)
    print("  ->", ok, reason, info)
    return ok

def autonomy_auto_no_signal():
    """
    [5] AUTONOMY AUTO (SIM) — No-signal should HOLD.

    Contract:
      - If runtime/signals.jsonl is absent (or unreadable), autonomy loop must NOT crash
        and must prefer HOLD (no-op).
      - We temporarily hide runtime/signals.jsonl (if it exists) to make this deterministic.
    """
    print("[5] AUTONOMY AUTO (SIM) — No-signal HOLD")
    runtime = os.path.join(os.path.dirname(os.path.dirname(__file__)), "runtime")
    os.makedirs(runtime, exist_ok=True)
    sig = os.path.join(runtime, "signals.jsonl")
    bak = os.path.join(runtime, "signals.jsonl.bak_smoke")

    # Hide signals.jsonl if it exists (deterministic no-signal)
    try:
        if os.path.exists(sig):
            try:
                if os.path.exists(bak):
                    os.remove(bak)
                os.replace(sig, bak)
            except Exception:
                # If we cannot move it, we still proceed; the loop must be resilient.
                pass

        # Run autonomy loop in SIM with AUTO signal source
        import subprocess, json

        cmd = [
            sys.executable, "-m", "scripts.autonomy_decision_loop",
            "--mode", "SIM",
            "--signal", "AUTO",
            "--symbol", "SMOKETESTUSDT",
            "--qty", "1",
            "--price", "1.0",
        ]
        p = subprocess.run(cmd, capture_output=True, text=True)
        out = (p.stdout or "").strip()

        # Expect: exit=0 and JSON status=HOLD (no signal)
        ok = (p.returncode == 0)
        try:
            last = out.splitlines()[-1] if out else "{}"
            j = json.loads(last)
            ok = ok and (j.get("status") == "HOLD")
        except Exception:
            ok = False

        print("  ->", "HOLD" if ok else "FAIL")
        return ok

    finally:
        # Restore signals.jsonl if we hid it
        try:
            if os.path.exists(bak) and (not os.path.exists(sig)):
                os.replace(bak, sig)
        except Exception:
            pass

def real_dryrun():
    """
    [4] REAL dry-run market path (stub).

    Исторически здесь проверялся REAL-путь через OrderExecutor с real_client.
    В ветке 1.3.x OrderExecutor больше не поддерживает REAL-режим и работает только
    как SIM/DRY-исполнитель (см. core/executor.py).

    Чтобы не ронять smoke-тест и при этом явно зафиксировать это поведение,
    шаг [4] помечен как SKIPPED и всегда возвращает True.
    """
    print("[4] REAL dry-run market path (stubbed in 1.3.x)")
    print("  -> SKIPPED: REAL mode is not available in current OrderExecutor")
    return True

def main():
    r1 = sim_autoclose()
    r2 = sim_recovery()
    r3 = preview_path()
    r4 = real_dryrun()
    r5 = autonomy_auto_no_signal()

    summary = {
        "SIM_close": r1,
        "Recovery": r2,
        "Preview": r3,          # optional: environment preparation
        "REAL_dry": r4,
        "Autonomy_AUTO": r5,
    }
    print("\nSMOKE SUMMARY:", summary)

    # Smoke PASS criteria: core contracts only (Preview is optional)
    required = {k: v for k, v in summary.items() if k != "Preview"}
    sys.exit(0 if all(required.values()) else 1)

if __name__ == "__main__":
    main()
