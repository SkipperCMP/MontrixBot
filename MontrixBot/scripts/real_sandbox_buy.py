
# scripts/real_sandbox_buy.py — ensure env loaded before any imports that need keys
from __future__ import annotations
import os, sys, getpass, math
try:
    from tools.env_force_load import ensure_env_loaded
    ensure_env_loaded()
except Exception:
    pass

def ask(prompt, default=None):
    v = input(f"{prompt}" + (f" [{default}]" if default else "") + ": ").strip()
    return v or (default or "")

def public_price(symbol: str):
    try:
        from binance.client import Client
        cli = Client()  # public-only
        t = cli.get_symbol_ticker(symbol=symbol)
        return float(t["price"])
    except Exception:
        return None

def step_round(v, step):
    if not step or step <= 0: return v
    return math.floor(v/step)*step

def main():
    root = os.path.dirname(os.path.dirname(__file__))
    sys.path.insert(0, root)

    symbol = (sys.argv[1] if len(sys.argv)>1 else ask("Symbol","ADAUSDT")).upper()

    price = public_price(symbol)
    if price is None:
        price = float(ask("Current price (manual)"))

    # filters
    from core.binance_filters import load_filters, hard_round_and_validate
    sf = load_filters(symbol)

    min_qty_guess = (sf.min_notional or 0.0) / max(price, 1e-12)
    qty = step_round(min_qty_guess, sf.step_size or 0.0)
    if qty <= 0:
        qty = sf.min_qty or min_qty_guess

    print(f"[INFO] price≈{price}, min_notional={sf.min_notional}, step_size={sf.step_size}, min_qty={sf.min_qty}")
    print(f"[INFO] computed qty={qty}")
    qty = float(ask("Quantity (ENTER to keep)", f"{qty}"))

    rp, rq, ok, _ = hard_round_and_validate(symbol, price, qty)
    if not ok:
        # auto-bump qty slightly to satisfy minNotional after price rounding
        step = sf.step_size or 0.01
        rq = step_round((sf.min_notional + 1e-6) / max(rp, 1e-12), step)
        print(f"[AUTO] bumped rq to {rq} to satisfy minNotional at rp={rp}")

    safe_code = getpass.getpass("SAFE code: ").strip()
    confirm_token = None
    for a in sys.argv[1:]:
        if isinstance(a, str) and a.strip().lower().startswith("confirm="):
            confirm_token = a.split("=", 1)[1].strip()

    if not confirm_token:
        from core.risky_confirm import RiskyConfirmService
        cmd_text = f"/real_sandbox_buy {symbol} qty={rq}"
        pending = RiskyConfirmService().request(cmd_text, actor="local", ttl_s=60)
        print("⚠️ Confirmation required.")
        print(f"Repeat the SAME command with:\npython scripts/real_sandbox_buy.py {symbol} {qty} confirm={pending.token}")
        raise SystemExit(2)

    from core.orders_real import place_order_real
    resp = place_order_real(
        symbol, "BUY",
        type_="MARKET",
        quantity=rq,
        safe_code=safe_code,
        confirm_token=confirm_token,
        confirm_actor="local",
    )
    print(json.dumps(resp, ensure_ascii=False))

if __name__ == "__main__":
    main()
