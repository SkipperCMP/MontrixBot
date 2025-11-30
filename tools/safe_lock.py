
# tools/safe_lock.py — file-based 2FA-like SAFE lock for REAL orders (1.0.1+)
import os
SAFE_FLAG = "SAFE_MODE"
UNLOCK_FILE = os.path.join("runtime", "safe_unlock.key")

def is_safe_on() -> bool:
    return os.path.exists(SAFE_FLAG)

def require_unlock(code: str) -> bool:
    try:
        with open(UNLOCK_FILE, "r", encoding="utf-8") as f:
            key = (f.read() or "").strip()
    except Exception:
        key = ""
    return bool(code and key and code == key)

def set_unlock_key(code: str):
    os.makedirs("runtime", exist_ok=True)
    with open(UNLOCK_FILE, "w", encoding="utf-8") as f:
        f.write(code.strip())

def enable_safe():
    with open(SAFE_FLAG, "w", encoding="utf-8") as f:
        f.write("SAFE")
    return True

def disable_safe():
    try:
        os.remove(SAFE_FLAG)
    except FileNotFoundError:
        pass
    return True
