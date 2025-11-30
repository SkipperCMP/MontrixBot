
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class SymbolFilters:
    min_qty: float = 0.0
    min_notional: float = 0.0

class RiskValidator:
    def __init__(self) -> None:
        self._filters: dict[str, SymbolFilters] = {}

    def set_filters(self, symbol: str, *, min_qty: float, min_notional: float) -> None:
        self._filters[symbol] = SymbolFilters(min_qty=min_qty, min_notional=min_notional)

    def validate(self, symbol: str, qty: float, price: float) -> bool:
        f = self._filters.get(symbol)
        if not f:
            return qty > 0 and price > 0
        if qty < f.min_qty:
            return False
        if qty * price < f.min_notional:
            return False
        return True
