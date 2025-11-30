
import os
import sys

SCHEMES = [
    ("GENERIC", ("API_KEY", "API_SECRET")),
    ("BINANCE", ("BINANCE_API_KEY", "BINANCE_SECRET")),
]

def _read_env(path: str) -> dict:
    data = {}
    if not os.path.exists(path):
        return data
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            data[k.strip()] = v.strip()
    return data

def check_env(path: str = ".env") -> bool:
    env = _read_env(path)
    if not env:
        print("[ENV] .env not found or empty")
        return False

    found_scheme = None
    ok = False
    details = []

    for name, (k1, k2) in SCHEMES:
        v1 = env.get(k1, "")
        v2 = env.get(k2, "")
        has1 = bool(v1)
        has2 = bool(v2)
        details.append(f"{name}: {k1}={has1}, {k2}={has2}")
        if has1 or has2:
            found_scheme = name if not found_scheme else found_scheme  # first match keeps precedence
        if has1 and has2:
            ok = True

    print("[ENV] Schemes status -> " + "; ".join(details))
    if found_scheme:
        print(f"[ENV] Detected scheme: {found_scheme}")
    else:
        print("[ENV] No known key scheme detected")

    if not ok:
        print("[ENV] Missing required key pair in .env (values not validated)")
    else:
        print("[ENV] Required fields present (values not validated)")
    return ok

if __name__ == "__main__":
    sys.exit(0 if check_env() else 1)
