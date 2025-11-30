from __future__ import annotations
import json, math, os
from dataclasses import dataclass
from typing import Dict, Any, Optional

# Кэш exchangeInfo, как его сохраняет MontrixBot
_CACHE_PATH = os.path.join("runtime", "exchange_info.json")


@dataclass
class SymbolFilters:
    tick_size: float = 0.0
    step_size: float = 0.0
    min_qty: float = 0.0
    min_notional: float = 0.0


def _round_step(x: float, step: float) -> float:
    if step <= 0:
        return float(x)
    # robust flooring without FP drift
    return math.floor((float(x) + 1e-12) / float(step)) * float(step)


def round_price(price: float, tick_size: float) -> float:
    return _round_step(float(price), float(tick_size))


def round_qty(qty: float, step_size: float) -> float:
    return _round_step(float(qty), float(step_size))


def load_cache() -> Dict[str, Any]:
    if os.path.exists(_CACHE_PATH):
        try:
            with open(_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            # на всякий случай — если там внезапно список, оборачиваем
            if isinstance(data, list):
                return {"symbols": data}
        except Exception:
            return {}
    return {}


def _extract_from_flat_dict(data: Dict[str, Any]) -> SymbolFilters:
    """Поддержка старого формата: уже «плоский» словарь по символу.

    Ожидаемые ключи:
      tickSize/stepSize/minQty/minNotional или их snake_case-варианты.
    """
    return SymbolFilters(
        tick_size=float(
            data.get("tickSize")
            or data.get("tick_size")
            or 0
        ),
        step_size=float(
            data.get("stepSize")
            or data.get("step_size")
            or 0
        ),
        min_qty=float(
            data.get("minQty")
            or data.get("min_qty")
            or 0
        ),
        min_notional=float(
            data.get("minNotional")
            or data.get("min_notional")
            or data.get("notional")
            or 0
        ),
    )


def _extract_from_symbol_obj(sym: Dict[str, Any]) -> SymbolFilters:
    """Поддержка сырого binance /exchangeInfo (symbol + filters[])."""
    tick_size = 0.0
    step_size = 0.0
    min_qty = 0.0
    min_notional = 0.0

    filters = sym.get("filters") or []
    for f in filters:
        ftype = f.get("filterType")
        if ftype == "PRICE_FILTER":
            tick_size = float(
                f.get("tickSize")
                or f.get("tick_size")
                or 0
            )
        elif ftype in ("LOT_SIZE", "MARKET_LOT_SIZE"):
            step_size = float(
                f.get("stepSize")
                or f.get("step_size")
                or 0
            )
            min_qty = float(
                f.get("minQty")
                or f.get("min_qty")
                or 0
            )
        elif ftype in ("MIN_NOTIONAL", "NOTIONAL"):
            min_notional = float(
                f.get("minNotional")
                or f.get("min_notional")
                or f.get("notional")
                or 0
            )

    return SymbolFilters(
        tick_size=tick_size,
        step_size=step_size,
        min_qty=min_qty,
        min_notional=min_notional,
    )


def get_filters(symbol: str) -> Optional[SymbolFilters]:
    """Возвращает фильтры для символа из runtime/exchange_info.json.

    Поддерживаются оба формата:
      1) Старый: { "symbols": { "ADAUSDT": {tickSize, stepSize, ...} } }
      2) Новый (сырой Binance): { "symbols": [ { "symbol": "ADAUSDT", "filters": [...] }, ... ] }
    """
    cache = load_cache()
    sym = symbol.upper()
    symbols = cache.get("symbols")

    if not symbols:
        return None

    # Вариант 1: словарь symbol -> dict с полями tickSize/stepSize/...
    if isinstance(symbols, dict):
        data = symbols.get(sym)
        if not isinstance(data, dict):
            return None
        return _extract_from_flat_dict(data)

    # Вариант 2: список сырых объектов Binance
    if isinstance(symbols, list):
        for item in symbols:
            if not isinstance(item, dict):
                continue
            if item.get("symbol") == sym or item.get("s") == sym:
                # если есть filters -> сырой объект Binance
                if "filters" in item:
                    return _extract_from_symbol_obj(item)
                # fallback: вдруг это уже плоский dict
                return _extract_from_flat_dict(item)

    return None


def validate(symbol: str, side: str, price: Optional[float], qty: float) -> tuple[bool, str, dict]:
    sf = get_filters(symbol)
    info: Dict[str, Any] = {}
    if sf:
        rq = round_qty(qty, sf.step_size) if sf.step_size else float(qty)
        rp = round_price(price, sf.tick_size) if (price is not None and sf.tick_size) else price
        info.update({"rounded_qty": rq, "rounded_price": rp})
        if rq < sf.min_qty and sf.min_qty > 0:
            return False, f"qty<{sf.min_qty}", info
        if rp is not None and sf.min_notional > 0 and rp * rq < sf.min_notional:
            return False, f"notional<{sf.min_notional}", info
    return True, "ok", info
