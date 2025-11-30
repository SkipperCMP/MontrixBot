
import os, sys, json, time, subprocess
from datetime import datetime

try:
    import psutil
except Exception:
    psutil = None

# recovery counter
try:
    from tools.recovery_counter import increment as recovery_increment
except Exception:
    def recovery_increment():
        return -1

def _is_exchange_info_broken(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            json.load(f)
        return False
    except Exception:
        return True

def ensure_exchange_info():
    root = os.path.dirname(__file__)
    path = os.path.normpath(os.path.join(root, "runtime", "exchange_info.json"))
    if (not os.path.exists(path)) or _is_exchange_info_broken(path):
        script = os.path.normpath(os.path.join(root, "tools", "fetch_exchange_info.py"))
        print("[HEALTH] exchange_info missing/corrupt -> restoring…")
        subprocess.run([sys.executable, script], check=False)
        cnt = recovery_increment()
        if cnt >= 0:
            print(f"[RECOVERY] consecutive={cnt} (exchange_info restore)")

HEALTH_LOG = os.path.normpath(os.path.join(os.path.dirname(__file__), "runtime", "health_log.jsonl"))

def write_snapshot(extra=None):
    snap = {
        "ts": datetime.utcnow().isoformat() + "Z",
    }
    if psutil:
        try:
            vm = psutil.virtual_memory()
            snap["cpu"] = psutil.cpu_percent(interval=None)
            snap["mem"] = {"total": vm.total, "used": vm.used, "percent": vm.percent}
            snap["threads"] = len(psutil.Process().threads())
        except Exception as e:
            snap["psutil_error"] = str(e)
    if extra:
        snap.update(extra)
    os.makedirs(os.path.dirname(HEALTH_LOG), exist_ok=True)
    with open(HEALTH_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(snap, ensure_ascii=False) + "\n")

def main():
    ensure_exchange_info()
    print("[HEALTH] monitor started")
    while True:
        write_snapshot()
        time.sleep(30)

if __name__ == "__main__":
    sys.exit(main())
