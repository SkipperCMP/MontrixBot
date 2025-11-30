
from __future__ import annotations

from typing import Dict

from .active_position import ActivePositionEngine


class SimTradeEngine:
    """Thin wrapper used by AutoSimFromSignals."""

    def __init__(self, initial_balance: float = 1000.0) -> None:
        self._engine = ActivePositionEngine(initial_balance=initial_balance)

    @property
    def active_positions(self):
        return self._engine.active_positions

    @property
    def closed_trades(self):
        return self._engine.closed_trades

    def process(
        self,
        symbol: str,
        last_price: float,
        signal_side: str,
        recommendation_side: str,
    ) -> Dict:
        return self._engine.process_signal(
            symbol=symbol,
            last_price=last_price,
            signal_side=signal_side,
            recommendation_side=recommendation_side,
        )

