
import os, time

FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'runtime', 'recovery_counter.txt'))
STAMP = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'runtime', 'last_recovery.stamp'))

def increment() -> int:
    os.makedirs(os.path.dirname(FILE), exist_ok=True)
    n = 0
    if os.path.exists(FILE):
        try:
            with open(FILE, "r", encoding="utf-8") as f:
                n = int((f.read() or "0").strip())
        except:
            n = 0
    n += 1
    with open(FILE, "w", encoding="utf-8") as f:
        f.write(str(n))
    with open(STAMP, "w", encoding="utf-8") as f:
        f.write(str(int(time.time())))
    return n

def read() -> int:
    try:
        with open(FILE, "r", encoding="utf-8") as f:
            return int((f.read() or "0").strip())
    except:
        return 0

def reset():
    try: os.remove(FILE)
    except: pass
