#!/usr/bin/env python3
import time, json, subprocess, sys, os
from datetime import datetime

os.makedirs("logs", exist_ok=True)
JSONL = os.path.join("logs","health_24h.jsonl")

def one_tick():
    cmd = [sys.executable, os.path.join("scripts","health_monitor.py")]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=300)
        # try parse simple JSON dict from the output tail if present
        text = out.strip().splitlines()
        last = text[-1] if text else ""
        payload = None
        try:
            payload = json.loads(last)
        except Exception:
            payload = {"raw": last}
        payload.setdefault("ts", datetime.utcnow().isoformat()+"Z")
        with open(JSONL,"a",encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False)+"\n")
        print(last)
    except subprocess.CalledProcessError as e:
        print(e.output.strip())
    except Exception as e:
        print(f"[HEALTH_PLUS] Exception: {e}")

if __name__=="__main__":
    if "--loop" in sys.argv:
        while True:
            one_tick()
            time.sleep(60)
    else:
        one_tick()
