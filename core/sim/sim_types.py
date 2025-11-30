
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class SimPosition:
    symbol: str
    side: str  # "LONG" only for now
    qty: float
    entry_price: float
    current_price: float
    tp: float
    sl: float
    opened_ts: float
    hold_days: float = 0.0

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.entry_price <= 0:
            return 0.0
        return (self.current_price - self.entry_price) / self.entry_price * 100.0


@dataclass
class SimTrade:
    symbol: str
    side: str
    qty: float
    entry_price: float
    exit_price: float
    pnl_pct: float
    opened_ts: float
    closed_ts: float


@dataclass
class SimPortfolio:
    balance: float
    equity: float
    open_positions_count: int
    positions: List[SimPosition] = field(default_factory=list)
    closed_trades: List[SimTrade] = field(default_factory=list)

