"""
MontrixBot 0.9.5 — Step 4.2
Integration controller (core) for TP/SL/Tier-logic inside SIM

Aggressive v1 (baseline confirmed):
- TP1: +1.5%
- TP2: +3.0%
- TP3: +5.0%
- Start SL: -1.2%
- Tier1 on TP1:       SL := entry
- Tier2 on TP2:       SL := entry + 0.3%
- Tier3 on TP3:       SL := trailing (distance 0.8%)

This module is **SIM-only**. It does not place or modify any real orders.
It maintains per-position state and reacts to incoming price updates, producing
HOLD/CLOSE decisions and updated TP/SL/tier state.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, Optional, Tuple, Any
import math


class Action(str, Enum):
    HOLD = "HOLD"
    CLOSE = "CLOSE"


@dataclass
class TierConfig:
    tp1: float = 0.015   # +1.5%
    tp2: float = 0.030   # +3.0%
    tp3: float = 0.050   # +5.0%
    start_sl: float = -0.012   # -1.2%
    tier2_sl_above_entry: float = 0.003  # +0.3%
    trail_dist: float = 0.008  # 0.8% trailing distance in Tier3


@dataclass
class PositionState:
    symbol: str
    qty: float
    entry_price: float
    # dynamic elements
    current_tier: int = 0  # 0..3
    current_dynamic_sl: Optional[float] = None
    tp1_level: Optional[float] = None
    tp2_level: Optional[float] = None
    tp3_level: Optional[float] = None
    realized_at: Optional[float] = None  # timestamp
    result_pnl_pct: Optional[float] = None
    # bookkeeping
    last_price: Optional[float] = None
    last_update_ts: Optional[float] = None

    def to_json(self) -> Dict[str, Any]:
        return asdict(self)


class TierEngine:
    """Tier engine core for Aggressive v1 TP/SL logic (SIM).

    Usage pattern:
        engine = TierEngine(cfg=TierConfig())
        pos = engine.open_position(symbol="ADAUSDT", qty=100, entry_price=0.5)
        action, state = engine.on_price(pos, price=0.505, ts=...)
        if action == Action.CLOSE:
            # handle close in SIM (book PnL, remove position, etc.)
            ...

    Notes:
        - Price feed is external; engine is stateless apart from PositionState passed in.
        - No I/O or exchange calls here. Pure decision logic.
    """

    def __init__(self, cfg: Optional[TierConfig] = None):
        self.cfg = cfg or TierConfig()

    # ------------------------ public API ------------------------ #
    def open_position(self, symbol: str, qty: float, entry_price: float) -> PositionState:
        ps = PositionState(symbol=symbol, qty=qty, entry_price=entry_price)
        # initialize SL and TP levels
        ps.current_tier = 0
        ps.current_dynamic_sl = self._sl_from(entry_price, self.cfg.start_sl)
        ps.tp1_level = self._tp_from(entry_price, self.cfg.tp1)
        ps.tp2_level = self._tp_from(entry_price, self.cfg.tp2)
        ps.tp3_level = self._tp_from(entry_price, self.cfg.tp3)
        return ps

    def on_price(self, ps: PositionState, price: float, ts: Optional[float] = None) -> Tuple[Action, PositionState]:
        """Feed one price tick. Returns the decision and possibly updated state.

        The order of checks is important:
        1) Check SL breach → CLOSE
        2) Check TP3/TP2/TP1 hits (tier upgrades) → adjust SL/tier (may still HOLD)
        3) In Tier3 apply trailing update
        """
        ps.last_price = price
        ps.last_update_ts = ts

        # 1) stop-loss check
        if ps.current_dynamic_sl is not None and price <= ps.current_dynamic_sl:
            return self._close(ps, price, ts)

        # 2) tiers (check from highest to lowest so we don't miss cascades)
        tier_upgraded = False
        if ps.current_tier < 3 and price >= ps.tp3_level:
            self._upgrade_to_tier3(ps)
            tier_upgraded = True
        elif ps.current_tier < 2 and price >= ps.tp2_level:
            self._upgrade_to_tier2(ps)
            tier_upgraded = True
        elif ps.current_tier < 1 and price >= ps.tp1_level:
            self._upgrade_to_tier1(ps)
            tier_upgraded = True

        # 3) trailing in Tier3 (only HOLD path)
        if ps.current_tier == 3:
            self._apply_trailing(ps, price)

        # re-check SL after tier changes/trailing tighten
        if ps.current_dynamic_sl is not None and price <= ps.current_dynamic_sl:
            return self._close(ps, price, ts)

        return Action.HOLD, ps

    # ------------------------ internals ------------------------ #

    def _close(self, ps: PositionState, price: float, ts: Optional[float]) -> Tuple[Action, PositionState]:
        pnl_pct = self._pnl_pct(ps.entry_price, price)
        ps.realized_at = ts
        ps.result_pnl_pct = pnl_pct
        return Action.CLOSE, ps

    def _upgrade_to_tier1(self, ps: PositionState) -> None:
        ps.current_tier = max(ps.current_tier, 1)
        ps.current_dynamic_sl = ps.entry_price  # move SL to break-even

    def _upgrade_to_tier2(self, ps: PositionState) -> None:
        ps.current_tier = max(ps.current_tier, 2)
        ps.current_dynamic_sl = self._tp_from(ps.entry_price, self.cfg.tier2_sl_above_entry)

    def _upgrade_to_tier3(self, ps: PositionState) -> None:
        ps.current_tier = 3
        # initialize trailing at (price - trail_dist)
        if ps.last_price is not None:
            trail = ps.last_price * (1.0 - self.cfg.trail_dist)
            ps.current_dynamic_sl = max(ps.current_dynamic_sl or -math.inf, trail)
        else:
            # fallback to tier2 rule if no price yet
            ps.current_dynamic_sl = self._tp_from(ps.entry_price, self.cfg.tier2_sl_above_entry)

    def _apply_trailing(self, ps: PositionState, price: float) -> None:
        # tighten SL only upwards (never lower it)
        desired = price * (1.0 - self.cfg.trail_dist)
        if ps.current_dynamic_sl is None:
            ps.current_dynamic_sl = desired
        else:
            ps.current_dynamic_sl = max(ps.current_dynamic_sl, desired)

    # ------------------------ helpers ------------------------ #

    @staticmethod
    def _tp_from(entry: float, pct: float) -> float:
        return entry * (1.0 + pct)

    @staticmethod
    def _sl_from(entry: float, pct: float) -> float:
        return entry * (1.0 + pct)

    @staticmethod
    def _pnl_pct(entry: float, price: float) -> float:
        if entry == 0:
            return 0.0
        return (price / entry - 1.0) * 100.0


# ------------------------ quick self-test (manual) ------------------------ #
if __name__ == "__main__":
    eng = TierEngine()
    pos = eng.open_position("TESTUSDT", qty=10, entry_price=100.0)
    stream = [99.0, 100.0, 101.6, 103.5, 104.0, 103.0, 102.0, 101.0, 100.0]
    ts = 0
    for p in stream:
        ts += 1
        act, state = eng.on_price(pos, p, ts)
        print(f"t={ts} price={p:.2f} act={act} tier={state.current_tier} sl={state.current_dynamic_sl:.4f}")
        if act == Action.CLOSE:
            print("CLOSED PnL=", state.result_pnl_pct)
            break
