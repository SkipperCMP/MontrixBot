
# scripts/real_buy_market.py — CLI bridge for UI button (fixed sys.path root)
from __future__ import annotations
import os, sys, getpass, json, math, pathlib

# ensure project root on sys.path (so "core" is importable when run via path)
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# load .env
try:
    from tools.env_force_load import ensure_env_loaded
    ensure_env_loaded()
except Exception:
    pass

def step_round(v, step):
    if not step or step <= 0: return v
    return math.floor(v/step)*step

def read_safe_code():
    p = os.path.join("runtime", "safe_unlock.key")
    if os.path.exists(p):
        try:
            return open(p, "r", encoding="utf-8").read().strip()
        except Exception:
            return None
    return None

def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/real_buy_market.py SYMBOL QTY [--ask]")
        sys.exit(2)
    symbol = sys.argv[1].upper()
    qty = float(sys.argv[2])
    ask_mode = ("--ask" in sys.argv)

    # get public price (optional)
    price = None
    try:
        from binance.client import Client
        price = float(Client().get_symbol_ticker(symbol=symbol)["price"])
    except Exception:
        pass

    from core.binance_filters import hard_round_and_validate, load_filters
    if price is None:
        price = 1.0  # for notional calc fallback
    rp, rq, ok, sf = hard_round_and_validate(symbol, price, qty)
    if not ok:
        step = sf.step_size or 0.01
        rq = step_round((sf.min_notional + 1e-6) / max(rp, 1e-12), step)

    safe_code = read_safe_code()
    if ask_mode or not safe_code:
        safe_code = getpass.getpass("SAFE code: ").strip()

    from core.orders_real import place_order_real
    resp = place_order_real(symbol, "BUY", type_="MARKET", quantity=rq, safe_code=safe_code)
    print(json.dumps(resp, ensure_ascii=False))

if __name__ == "__main__":
    main()
