
from __future__ import annotations
from typing import Dict, Any, List

def select_open_positions(state_snap: Dict[str, Any]) -> List[dict]:
    out = []
    positions = state_snap.get("positions", {})
    ticks = state_snap.get("ticks", {})
    for sym, pos in positions.items():
        if pos.get("status") != "OPEN":
            continue
        last = ticks.get(sym, {}).get("last")
        out.append({
            "symbol": sym,
            "qty": pos.get("qty", 0.0),
            "avg_price": pos.get("avg_price", 0.0),
            "last": last,
            "unrealized_pnl": pos.get("unrealized_pnl", 0.0),
            "status": pos.get("status", "OPEN"),
        })
    return out

def select_orders_normalized(state_snap: Dict[str, Any]) -> List[dict]:
    """Возвращает массив уже агрегированных ордеров (после 4.1)."""
    ords = state_snap.get("orders", {})
    if isinstance(ords, dict):
        return list(ords.values())
    if isinstance(ords, list):
        return ords
    return []


def select_deals_journal(state_snap: Dict[str, Any]) -> List[dict]:
    j = state_snap.get("journal", [])
    if isinstance(j, list):
        return j
    return []


def select_last_deal(state_snap: Dict[str, Any]) -> Dict[str, Any] | None:
    j = state_snap.get("journal", [])
    if not isinstance(j, list) or not j:
        return None
    try:
        # choose max by ts
        return max(j, key=lambda r: r.get("ts", 0))
    except Exception:
        return j[-1]
