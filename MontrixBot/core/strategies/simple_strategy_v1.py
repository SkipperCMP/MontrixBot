# core/strategies/simple_strategy_v1.py
# v2.2.52 — First Simple Strategy (SIM-only, events-only)
#
# Reads (signal, recommendation, meta) from UIAPI.update_advisor_snapshot
# and emits rare SIM_DECISION_JOURNAL entries into the persisted event spine.
#
# IMPORTANT:
# - No REAL power, no trading, no side-effects besides appending event.
# - Must never break the caller.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import time

from core.event_bus import get_event_bus, make_event, new_cid


@dataclass
class _DecisionMem:
    last_ts: float = 0.0
    last_action: str = ""
    last_key: str = ""


def _sf(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def maybe_publish_sim_decision_journal(
    mem_by_symbol: Dict[str, _DecisionMem],
    signal: Optional[Dict[str, Any]],
    recommendation: Optional[Dict[str, Any]],
    meta: Optional[Dict[str, Any]],
) -> bool:
    """
    Returns True if published.

    Filter rules (v1):
    - reco side must be BUY/SELL
    - confidence must be >= 0.60
    - per-symbol cooldown: 30 seconds
    - publish only if (action changed) OR (key changed) after cooldown
    """
    try:
        sig = signal or {}
        reco = recommendation or {}
        m = meta or {}

        symbol = str(m.get("symbol") or "").upper() or "UNKNOWN"

        action = str(reco.get("side") or "HOLD").upper()
        conf = _sf(reco.get("strength"), 0.0)

        if action not in ("BUY", "SELL"):
            return False
        if conf < 0.60:
            return False

        reason = str(reco.get("reason") or "")
        trend = str(reco.get("trend") or "")
        score = _sf(reco.get("score"), conf)

        # key captures meaningful change
        key = f"{action}|{round(conf,2)}|{trend}|{reason[:120]}"

        mem = mem_by_symbol.get(symbol)
        if mem is None:
            mem = _DecisionMem()
            mem_by_symbol[symbol] = mem

        now = time.time()
        cooldown_ok = (now - float(mem.last_ts or 0.0)) >= 30.0

        # publish only on change OR after cooldown with a changed key
        changed_action = (action != (mem.last_action or ""))
        changed_key = (key != (mem.last_key or ""))

        if not (changed_action or (cooldown_ok and changed_key)):
            return False

        # Build payload (contract-compatible with existing UI Journal viewer)
        payload = {
            "strategy_sid": "trend_pulse",  # first simple strategy wired to v1 contract id
            "hypothesis": reason,
            "signals": {
                "symbol": symbol,
                "input_side": str(sig.get("side") or m.get("side") or "HOLD"),
                "rsi": m.get("rsi"),
                "macd": m.get("macd"),
                "macd_signal": m.get("macd_signal"),
                "trend": trend,
                "score": float(score),
            },
            "confidence": float(conf),
            "recommended_action": action,
        }

        bus = get_event_bus()
        cid = new_cid()
        bus.publish(make_event("SIM_DECISION_JOURNAL", payload, actor="sim", cid=cid))

        mem.last_ts = now
        mem.last_action = action
        mem.last_key = key
        return True
    except Exception:
        return False
