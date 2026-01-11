
# scripts/real_sell_market.py — REAL SELL (v5)
# - Prefer MARKET_LOT_SIZE only if stepSize>0; otherwise fallback to LOT_SIZE
# - Enforce minQty, stepSize, minNotional with Decimal rounding
# - Log chosen filter source (e.g., "(LOT_SIZE fallback)")
# - SAFE: asks code by default; supports --no-ask
from __future__ import annotations
import os, sys, json, getpass, pathlib
from decimal import Decimal, getcontext, ROUND_DOWN

getcontext().prec = 28

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Ensure .env is loaded
try:
    from tools.env_force_load import ensure_env_loaded
    ensure_env_loaded()
except Exception:
    pass

def d(x): return Decimal(str(x))

def read_safe_file() -> str | None:
    p = ROOT / "runtime" / "safe_unlock.key"
    try:
        return p.read_text(encoding="utf-8").strip()
    except Exception:
        return None

def load_exchange_info() -> dict | None:
    # Prefer local snapshot
    p = ROOT / "runtime" / "exchange_info.json"
    try:
        import json
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    # Fallback to live
    try:
        from binance.client import Client
        cli = Client()
        return cli.get_exchange_info()
    except Exception:
        return None

def find_symbol_filters(symbol: str) -> dict:
    info = load_exchange_info() or {}
    symbols = info.get("symbols") or info.get("symbolsData") or []
    if isinstance(symbols, dict):
        symbols = symbols.values()
    for s in symbols:
        if (s.get("symbol") or "").upper() == symbol.upper():
            flt = {}
            for f in s.get("filters", []):
                ftype = f.get("filterType") or f.get("filter_type") or ""
                flt[ftype] = f
            return flt
    return {}

def extract_numbers(filters: dict) -> tuple[Decimal, Decimal, Decimal, str]:
    # Try MARKET_LOT_SIZE first
    src = "MARKET_LOT_SIZE"
    step = d("0")
    min_qty = d("0")
    if "MARKET_LOT_SIZE" in filters:
        try:
            step = d(filters["MARKET_LOT_SIZE"].get("stepSize", "0"))
            min_qty = d(filters["MARKET_LOT_SIZE"].get("minQty", "0"))
        except Exception:
            step, min_qty = d("0"), d("0")
    # If MARKET_LOT_SIZE unusable -> fallback to LOT_SIZE
    if step == 0:
        src = "LOT_SIZE fallback"
        if "LOT_SIZE" in filters:
            step = d(filters["LOT_SIZE"].get("stepSize", "0"))
            min_qty = d(filters["LOT_SIZE"].get("minQty", "0"))
        else:
            step, min_qty = d("0"), d("0")

    # MIN_NOTIONAL / NOTIONAL
    min_notional = d("0")
    if "MIN_NOTIONAL" in filters and filters["MIN_NOTIONAL"].get("minNotional"):
        min_notional = d(filters["MIN_NOTIONAL"]["minNotional"])
    elif "NOTIONAL" in filters and filters["NOTIONAL"].get("minNotional"):
        min_notional = d(filters["NOTIONAL"]["minNotional"])

    return step, min_qty, min_notional, src

def public_price(symbol: str) -> Decimal | None:
    try:
        from binance.client import Client
        cli = Client()
        t = cli.get_symbol_ticker(symbol=symbol)
        return d(t["price"])
    except Exception:
        return None

def quant_floor(x: Decimal, step: Decimal) -> Decimal:
    if step <= 0: return x
    return (x / step).to_integral_value(rounding=ROUND_DOWN) * step

def quant_ceil(x: Decimal, step: Decimal) -> Decimal:
    if step <= 0: return x
    q = (x / step).to_integral_value(rounding=ROUND_DOWN) * step
    if q < x: q += step
    return q

def format_qty(q: Decimal, step: Decimal) -> str:
    if step <= 0:
        return format(q.normalize(), 'f')
    s = format(step.normalize(), 'f')
    dp = len(s.split('.')[1]) if '.' in s else 0
    return f"{q:.{dp}f}"

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2:
        print("Usage: python scripts/real_sell_market.py SYMBOL QTY [--no-ask]")
        sys.exit(2)
    symbol = argv[0].upper()
    qty_in = d(argv[1])
    ask_mode = ("--no-ask" not in argv[2:])

    # SAFE flag
    if (ROOT / "SAFE_MODE").exists():
        raise PermissionError("SAFE is ON — remove SAFE_MODE to allow REAL orders")

    # Load filters and price
    filters = find_symbol_filters(symbol)
    step, min_qty, min_notional, source = extract_numbers(filters)
    price = public_price(symbol) or d("1")

    # Print chosen filters
    print(f"[FILTER] step={step}, minQty={min_qty}, minNotional={min_notional} ({source})")

    # Compute qty respecting step/minQty/minNotional
    q = qty_in
    if step > 0:
        q = quant_floor(q, step)
    if min_qty > 0 and q < min_qty:
        q = quant_ceil(min_qty, step if step > 0 else d("0.00000001"))
    if min_notional > 0 and (price * q) < min_notional:
        target = min_notional / (price if price > 0 else d("1"))
        q = quant_ceil(target, step if step > 0 else d("0.00000001"))
    if q <= 0:
        q = min_qty if min_qty > 0 else (step if step > 0 else d("1"))

    qty_str = format_qty(q, step if step > 0 else d("0.00000001"))

    # SAFE code
    safe_file = read_safe_file()
    if ask_mode:
        code = getpass.getpass("SAFE code: ").strip()
        if safe_file and code != safe_file:
            raise PermissionError("SAFE is ON — invalid unlock code")
        safe_code = code
    else:
        safe_code = safe_file

    # Two-step manual confirm (v2.2.105):
    confirm_token = None
    for a in sys.argv[1:]:
        if isinstance(a, str) and a.strip().lower().startswith("confirm="):
            confirm_token = a.split("=", 1)[1].strip()

    if not confirm_token:
        from core.risky_confirm import RiskyConfirmService
        cmd_text = f"/real_sell_market {symbol} qty={float(q)}"
        pending = RiskyConfirmService().request(cmd_text, actor="local", ttl_s=60)
        print("⚠️ Confirmation required.")
        print(f"Repeat the SAME command with:\npython scripts/real_sell_market.py {symbol} {q} confirm={pending.token}")
        raise SystemExit(2)

    # Place REAL SELL
    from core.orders_real import place_order_real
    resp = place_order_real(
        symbol, "SELL",
        type_="MARKET",
        quantity=float(q),
        safe_code=safe_code,
        confirm_token=confirm_token,
        confirm_actor="local",
    )
    print(json.dumps(resp, ensure_ascii=False))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Order failed:", type(e).__name__, str(e))
        sys.exit(1)
