#!/usr/bin/env python3
"""auto_smoke_test.py — единый смоук-тест для MontrixBot 1.0.1

ВНИМАНИЕ (1.0.1):
- В этот смоук включены только стабильные оффлайн-тесты ядра:
    1) smoke_run.py          — snapshot + dry_order + runtime_folder
    2) tools/smoke_sim.py    — SIM/TPSL + StateEngine ticks

- Скрипт scripts/smoke_run.py в 1.0.1 считается *legacy*-тестом
  и может не соответствовать текущей сигнатуре OrderExecutor,
  поэтому в общий авто-смоук не включён.

- Дополнительный real-тест (tools/real_smoke.py) запускается ТОЛЬКО,
  если явно задана переменная окружения MONTRIX_REAL_SMOKE=1.
"""
import os
import sys
import time
import subprocess
from typing import List, Tuple


ROOT = os.path.dirname(os.path.abspath(__file__))


def run_case(name: str, cmd: List[str]) -> Tuple[bool, float, str]:
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        dt = time.perf_counter() - t0
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        full_out = "\n".join(x for x in [out, err] if x)
        print(f"[SMOKE] {name}: OK ({dt:.2f}s)")
        if full_out:
            print(f"--- {name} output ---")
            print(full_out)
            print(f"--- end {name} ---")
        return True, dt, full_out
    except subprocess.CalledProcessError as e:
        dt = time.perf_counter() - t0
        out = (e.stdout or "").strip()
        err = (e.stderr or "").strip()
        full_out = "\n".join(x for x in [out, err] if x)
        print(f"[SMOKE] {name}: FAIL ({dt:.2f}s), code={e.returncode}")
        if full_out:
            print(f"--- {name} output ---")
            print(full_out)
            print(f"--- end {name} ---")
        return False, dt, full_out
    except Exception as e:
        dt = time.perf_counter() - t0
        print(f"[SMOKE] {name}: ERROR ({dt:.2f}s): {e}")
        return False, dt, str(e)


def main() -> int:
    print("=== MontrixBot 1.0.1 — AUTO SMOKE TEST ===")
    print(f"ROOT: {ROOT}")
    print()

    python = sys.executable

    # Только стабильные оффлайн-тесты 1.0.1:
    cases: List[Tuple[str, List[str]]] = [
        ("core_smoke_root", [python, "smoke_run.py"]),
        ("sim_tpsl_smoke",  [python, os.path.join("tools", "smoke_sim.py")]),
    ]

    # Опционально: real_smoke (SAFE/time), если явно включён
    if os.environ.get("MONTRIX_REAL_SMOKE") == "1":
        cases.append(
            ("real_safe_time_smoke", [python, os.path.join("tools", "real_smoke.py")])
        )

    all_ok = True
    summary = []

    for name, cmd in cases:
        print(f">>> RUN {name}: {' '.join(cmd)}")
        ok, dt, _ = run_case(name, cmd)
        summary.append((name, ok, dt))
        all_ok = all_ok and ok
        print()

    print("=== SUMMARY ===")
    for name, ok, dt in summary:
        status = "OK" if ok else "FAIL"
        print(f"{name:24s} : {status:4s} ({dt:.2f}s)")

    if all_ok:
        print("\n[RESULT] ✅ Все тесты пройдены успешно.")
        return 0
    else:
        print("\n[RESULT] ❌ Есть проваленные тесты, см. логи выше.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
