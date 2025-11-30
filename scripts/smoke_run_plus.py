#!/usr/bin/env python3
import time, json, subprocess, sys, os, shlex
from datetime import datetime

LOG = os.path.join("logs", "smoke_cycle.log")
os.makedirs("logs", exist_ok=True)

def run_once():
    start = time.time()
    # call the original script
    cmd = [sys.executable, os.path.join("scripts","smoke_run.py")]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=300)
        ok = True
        reason = "OK"
    except subprocess.CalledProcessError as e:
        out = e.output
        ok = False
        reason = "ERROR"
    except Exception as e:
        out = str(e)
        ok = False
        reason = "EXC"
    dur = time.time()-start
    line = f'{{"ts":"{datetime.utcnow().isoformat()}Z","ok":{str(ok).lower()},"dur_sec":{dur:.2f}}}'
    with open(LOG,"a",encoding="utf-8") as f:
        f.write(line+"\n")
    print(f"[SMOKE] {reason} ({dur:.2f}s)")
    if out:
        print(out.strip())

if __name__=="__main__":
    # loop each 1800s if --loop provided
    if "--loop" in sys.argv:
        while True:
            run_once()
            time.sleep(1800)
    else:
        run_once()
