
from __future__ import annotations
import json, os, math
from dataclasses import dataclass
from typing import Optional, Any

RUNTIME_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "runtime"))
EXCHANGE_INFO = os.path.join(RUNTIME_DIR, "exchange_info.json")

@dataclass
class SymbolFilters:
    price_tick: float = 0.0
    min_price: float = 0.0
    max_price: float = 0.0
    step_size: float = 0.0
    min_qty: float = 0.0
    max_qty: float = 0.0
    min_notional: float = 0.0

def _float(x) -> float:
    try: return float(x)
    except Exception: return 0.0

def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        txt = f.read().strip()
        # tolerate JSONL-like accidental content
        if "\n" in txt and txt.lstrip().startswith("{") and not txt.rstrip().endswith("}"):
            lines = [l for l in txt.splitlines() if l.strip()]
            try:
                return json.loads(lines[-1])
            except Exception:
                pass
        return json.loads(txt)

def _ensure_exchange_info_for(symbol: str) -> dict:
    try:
        data = _read_json(EXCHANGE_INFO)
    except Exception:
        data = {}

    symbols = []
    if isinstance(data, dict) and isinstance(data.get("symbols"), list):
        symbols = data["symbols"]
    elif isinstance(data, list):
        symbols = data
        data = {"symbols": symbols}
    else:
        data = {"symbols": []}
        symbols = []

    needs_fetch = False
    if symbols and isinstance(symbols[0], str):
        needs_fetch = True
    else:
        found = False
        for s in symbols:
            if isinstance(s, dict) and s.get("symbol") == symbol:
                found = True; break
        needs_fetch = not found

    if needs_fetch:
        try:
            from tools.fetch_exchange_info import fetch_and_merge
            data = fetch_and_merge([symbol], base=data, save_path=EXCHANGE_INFO)
        except Exception as e:
            raise RuntimeError(f"exchange_info.json missing/invalid and auto-fetch failed: {e}")

    return data

def load_filters(symbol: str) -> SymbolFilters:
    sym = symbol.upper()
    data = _ensure_exchange_info_for(sym)
    symbols = data.get("symbols") or []
    found = None
    for s in symbols:
        if isinstance(s, dict) and s.get("symbol") == sym:
            found = s; break
    if not found:
        raise ValueError(f"Symbol {sym} not found in exchange_info.json")

    sf = SymbolFilters()
    for flt in found.get("filters", []):
        t = flt.get("filterType")
        if t == "PRICE_FILTER":
            sf.price_tick = _float(flt.get("tickSize"))
            sf.min_price = _float(flt.get("minPrice"))
            sf.max_price = _float(flt.get("maxPrice"))
        elif t in ("LOT_SIZE", "MARKET_LOT_SIZE"):
            sf.step_size = _float(flt.get("stepSize"))
            sf.min_qty = max(sf.min_qty, _float(flt.get("minQty")))
            sf.max_qty = max(sf.max_qty, _float(flt.get("maxQty")))
        elif t in ("MIN_NOTIONAL", "NOTIONAL"):
            sf.min_notional = _float(flt.get("minNotional") or flt.get("notional"))
    return sf

def _step_round(value: float, step: float) -> float:
    if step <= 0: return value
    return math.floor(value/step) * step

def round_price(price: float, sf: SymbolFilters) -> float:
    p = max(sf.min_price, min(price, sf.max_price if sf.max_price>0 else price))
    if sf.price_tick > 0:
        p = _step_round(p, sf.price_tick)
    return float(f"{p:.10f}".rstrip("0").rstrip(".")) if "." in f"{p:.10f}" else float(p)

def round_qty(qty: float, sf: SymbolFilters) -> float:
    q = max(sf.min_qty, min(qty, sf.max_qty if sf.max_qty>0 else qty))
    if sf.step_size > 0:
        q = _step_round(q, sf.step_size)
    return float(f"{q:.10f}".rstrip("0").rstrip(".")) if "." in f"{q:.10f}" else float(q)

def validate_notional(price: float, qty: float, sf: SymbolFilters) -> bool:
    return (price or 0.0) * (qty or 0.0) >= sf.min_notional

def hard_round_and_validate(symbol: str, price: float, qty: float):
    sf = load_filters(symbol)
    rp = round_price(price, sf)
    rq = round_qty(qty, sf)
    ok_notional = validate_notional(rp, rq, sf)
    return rp, rq, ok_notional, sf
