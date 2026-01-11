
from __future__ import annotations

import time
from typing import List, Dict

from .sim_types import SimPosition, SimTrade, SimPortfolio


class ActivePositionEngine:
    """Very small single-symbol SIM engine."""

    def __init__(self, initial_balance: float = 1000.0) -> None:
        self.balance = float(initial_balance)
        self.active_positions: List[SimPosition] = []
        self.closed_trades: List[SimTrade] = []

    # simplified: 2 anchors + 1 rocket placeholder
    def process_signal(
        self,
        symbol: str,
        last_price: float,
        signal_side: str,
        recommendation_side: str,
    ) -> Dict:
        now = time.time()

        # very naive rules: if BUY -> open, if SELL -> close all
        if signal_side == "BUY":
            if not self.active_positions:
                qty = self.balance / max(last_price, 1e-8)
                self.balance = 0.0
                self.active_positions.append(
                    SimPosition(
                        symbol=symbol,
                        side="LONG",
                        qty=qty,
                        entry_price=last_price,
                        current_price=last_price,
                        tp=last_price * 1.04,
                        sl=last_price * 0.96,
                        opened_ts=now,
                    )
                )
        elif signal_side == "SELL":
            new_active: List[SimPosition] = []
            for pos in self.active_positions:
                pos.current_price = last_price
                pnl_pct = pos.unrealized_pnl_pct
                self.closed_trades.append(
                    SimTrade(
                        symbol=pos.symbol,
                        side="SELL",
                        qty=pos.qty,
                        entry_price=pos.entry_price,
                        exit_price=last_price,
                        pnl_pct=pnl_pct,
                        opened_ts=pos.opened_ts,
                        closed_ts=now,
                    )
                )
                self.balance += pos.qty * last_price
            self.active_positions = new_active

        # mark-to-market
        equity = self.balance
        for pos in self.active_positions:
            pos.current_price = last_price
            equity += pos.qty * last_price

        portfolio = SimPortfolio(
            balance=self.balance,
            equity=equity,
            open_positions_count=len(self.active_positions),
            positions=list(self.active_positions),
            closed_trades=list(self.closed_trades),
        )

        return {
            "portfolio": {
                "balance": portfolio.balance,
                "equity": portfolio.equity,
                "open_positions_count": portfolio.open_positions_count,
            },
            "active": [p.__dict__ for p in portfolio.positions],
            "closed": [t.__dict__ for t in portfolio.closed_trades[-50:]],
        }

