#!/usr/bin/env python3
# scripts/health_monitor_plus.py
# v2.2.104 — wrapper over Health Contract (snapshot-only; no file logs)

import sys
import time
import subprocess
import os


def one_tick() -> int:
    cmd = [sys.executable, os.path.join("scripts", "health_contract.py")]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=300)
        print(out.strip())
        return 0
    except subprocess.CalledProcessError as e:
        print(e.output.strip())
        return int(e.returncode or 1)
    except Exception as e:
        print(f"[HEALTH_PLUS] Exception: {e}")
        return 1


if __name__ == "__main__":
    if "--loop" in sys.argv:
        interval = 60
        try:
            i = sys.argv.index("--interval")
            interval = int(sys.argv[i + 1])
        except Exception:
            interval = int(os.environ.get("MTR_HEALTH_INTERVAL", "60") or "60")

        while True:
            one_tick()
            time.sleep(max(5, interval))
    else:
        raise SystemExit(one_tick())
