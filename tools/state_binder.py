import os, json, threading, time, shutil
from datetime import datetime

def rolling_checkpoint(src="runtime/state.json", dst_dir="runtime/checkpoints",
                       interval_sec=300, keep=12):
    """
    Periodically snapshots 'src' into 'dst_dir', keeping 'keep' latest files.
    Run as a daemon thread. Safe if src is missing.
    """
    os.makedirs(dst_dir, exist_ok=True)
    def _loop():
        while True:
            try:
                if os.path.exists(src):
                    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                    dst = os.path.join(dst_dir, f"state_{ts}.json")
                    tmp = dst + ".tmp"
                    shutil.copy2(src, tmp)
                    os.replace(tmp, dst)
                    files = sorted([f for f in os.listdir(dst_dir) if f.startswith("state_") and f.endswith(".json")])
                    for f in files[:-keep]:
                        try: os.remove(os.path.join(dst_dir, f))
                        except: pass
            except Exception as e:
                print(f"[STATE-BINDER] checkpoint error: {e}")
            time.sleep(interval_sec)
    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    return t
