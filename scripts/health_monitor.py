
# scripts/health_monitor.py
# MontrixBot 1.0 — passive health monitor
# Writes a heartbeat line to runtime/health.log every N seconds.
# Run separately from the main UI/process.

import os, sys, time, json
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(__file__))
RUNTIME = os.path.join(ROOT, "runtime")
os.makedirs(RUNTIME, exist_ok=True)

LOG = os.path.join(RUNTIME, "health.log")
TRADES = os.path.join(RUNTIME, "trades.jsonl")
EXINFO = os.path.join(RUNTIME, "exchange_info.json")
SAFE_FLAG = os.path.join(ROOT, "SAFE_MODE")
ENV_FILE = os.path.join(ROOT, ".env")

INTERVAL_SEC = int(os.environ.get("MTR_HEALTH_INTERVAL", "60"))  # default 60s

def parse_env(path):
    vals = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln or ln.startswith("#") or "=" not in ln:
                    continue
                k, v = ln.split("=", 1)
                vals[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return vals

def count_events():
    opens = 0
    closes = 0
    last_ts = None
    size = 0
    try:
        size = os.path.getsize(TRADES)
        with open(TRADES, "r", encoding="utf-8") as f:
            for ln in f:
                if '"type": "OPEN"' in ln:
                    opens += 1
                elif '"type": "CLOSE"' in ln:
                    closes += 1
                # try to extract ts field roughly
                idx = ln.rfind('"ts":')
                if idx != -1:
                    try:
                        ts_part = ln[idx+5:].split("}",1)[0]
                        ts_val = float("".join([ch for ch in ts_part if ch in "0123456789.-"]))
                        last_ts = ts_val
                    except Exception:
                        pass
    except FileNotFoundError:
        pass
    open_positions = max(0, opens - closes)
    return size, opens, closes, open_positions, last_ts

def fmt_ts(ts):
    try:
        return datetime.utcfromtimestamp(ts).isoformat() + "Z"
    except Exception:
        return None

def append_log(line):
    # rotate if > 1MB
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > 1024*1024:
            os.replace(LOG, LOG + ".1")
    except Exception:
        pass
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def main():
    env = parse_env(ENV_FILE)
    mode = env.get("MONTRIX_MODE", "SIM")
    dry = env.get("MONTRIX_DRY_RUN", "true")
    while True:
        now = datetime.utcnow().isoformat() + "Z"
        safe = os.path.exists(SAFE_FLAG)
        t_size, n_open, n_close, n_pos, last_ts = count_events()
        exinfo_ok = os.path.exists(EXINFO)
        exinfo_mtime = None
        try:
            exinfo_mtime = datetime.utcfromtimestamp(os.path.getmtime(EXINFO)).isoformat() + "Z" if exinfo_ok else None
        except Exception:
            pass
        line = json.dumps({
            "ts": now,
            "mode": mode,
            "dry_run": dry,
            "safe": safe,
            "trades_size": t_size,
            "events_open": n_open,
            "events_close": n_close,
            "open_positions_est": n_pos,
            "last_trade_ts": last_ts,
            "last_trade_iso": fmt_ts(last_ts) if last_ts else None,
            "exchange_info_present": exinfo_ok,
            "exchange_info_mtime": exinfo_mtime
        }, ensure_ascii=False)
        print(line)
        append_log(line)
        time.sleep(INTERVAL_SEC)

if __name__ == "__main__":
    main()
