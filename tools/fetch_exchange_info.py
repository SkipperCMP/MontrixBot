
from __future__ import annotations
import os, json, sys, requests
from typing import List, Dict, Any

RUNTIME_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "runtime"))
EXCHANGE_INFO = os.path.join(RUNTIME_DIR, "exchange_info.json")
API = "https://api.binance.com/api/v3/exchangeInfo"

def fetch(symbols: List[str] | None = None) -> Dict[str, Any]:
    params = {}
    if symbols:
        params["symbols"] = json.dumps([s.upper() for s in symbols])
    r = requests.get(API, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def fetch_and_merge(symbols: List[str] | None, base: Dict[str, Any] | None = None, save_path: str = EXCHANGE_INFO) -> Dict[str, Any]:
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    base = dict(base or {})
    base_symbols = base.get("symbols") or []
    if isinstance(base_symbols, list) and base_symbols and isinstance(base_symbols[0], str):
        base_symbols = []

    fresh = fetch(symbols)
    fresh_symbols = fresh.get("symbols") or []

    by_sym = {}
    for s in base_symbols:
        if isinstance(s, dict) and s.get("symbol"): by_sym[s["symbol"]] = s
    for s in fresh_symbols:
        if isinstance(s, dict) and s.get("symbol"): by_sym[s["symbol"]] = s

    merged = {"timezone": fresh.get("timezone") or base.get("timezone"),
              "serverTime": fresh.get("serverTime") or base.get("serverTime"),
              "symbols": list(by_sym.values()) or fresh_symbols}

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False)
    return merged

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a.strip()]
    if not args:
        data = fetch(None)
    else:
        data = fetch_and_merge(args, base=None)
    with open(EXCHANGE_INFO, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"[OK] exchange_info.json updated at {EXCHANGE_INFO}")
