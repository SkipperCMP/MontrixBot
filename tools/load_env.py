
# tools/load_env.py
import os, pathlib

def load_env(dotenv_path: str = ".env"):
    p = pathlib.Path(dotenv_path)
    if not p.exists():
        return False
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line=line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k,v = line.split("=",1)
        k=k.strip()
        v=v.strip()
        # basic boolean normalization
        if v.lower() in ("true","false"):
            os.environ[k] = v.lower()
        else:
            os.environ[k] = v
    return True
