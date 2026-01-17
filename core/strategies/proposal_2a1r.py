# core/strategies/proposal_2a1r.py
# v2.2.104 — Proposal Rename: avoid confusion with REAL Triple Strategy (v1.5)
#
# IMPORTANT:
# - SIM-only (analysis). No trading, no REAL power.
# - Deterministic: same inputs => same proposal.
# - IDLE-by-default: uncertainty => do nothing.
# - SAFE_MODE is absolute: SAFE_HARD_LOCK => IDLE.
#
# This is a *proposal heuristic*, NOT "Strategy: Rocket + 2 Anchors (v1.5)".

from __future__ import annotations

from typing import Any, Dict, Optional
import time


def _u(x: Any) -> str:
    try:
        return str(x or "").upper()
    except Exception:
        return ""


def _sf(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return float(default)
        return float(x)
    except Exception:
        return float(default)


def _is_safe_hard_lock() -> bool:
    # SAFE_MODE is a file-based hard lock (canonical in v1.2.0)
    try:
        from tools.safe_lock import is_safe_on
        return bool(is_safe_on())
    except Exception:
        return False


def compute_proposal(
    signal: Optional[Dict[str, Any]],
    recommendation: Optional[Dict[str, Any]],
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Returns proposal dict:
      - action: BUY/SELL/IDLE
      - confidence: 0..1
      - why / why_not: explainability
    """
    ts = int(time.time() * 1000)

    sym = ""
    try:
        sym = _u((meta or {}).get("symbol"))
    except Exception:
        sym = ""

    # SAFE HARD LOCK => absolute no-action
    if _is_safe_hard_lock():
        return {
            "name": "proposal_2a1r",
            "symbol": sym,
            "action": "IDLE",
            "confidence": 0.0,
            "why": "SAFE_HARD_LOCK active",
            "why_not": ["SAFE_HARD_LOCK"],
            "ts_ms": ts,
        }

    sig = signal or {}
    reco = recommendation or {}

    sig_side = _u(sig.get("side", "HOLD"))
    reco_side = _u(reco.get("side", "HOLD"))

    sig_strength = _sf(sig.get("strength"), 0.0)
    reco_strength = _sf(reco.get("strength"), 0.0)

    rsi = _sf(sig.get("rsi"), 0.0)
    macd = _sf(sig.get("macd"), 0.0)
    macd_sig = _sf(sig.get("macd_signal"), 0.0)

    why_not = []

    # Anchor #1: signal side must be explicit (BUY/SELL)
    anchor1 = sig_side in ("BUY", "SELL")
    if not anchor1:
        why_not.append("NO_SIGNAL")

    # Anchor #2: recommendation must confirm side and be strong enough
    min_reco = 0.55
    anchor2 = (reco_side == sig_side) and (reco_strength >= min_reco)
    if reco_side != sig_side and sig_side in ("BUY", "SELL"):
        why_not.append("SIDE_MISMATCH")
    if reco_strength < min_reco:
        why_not.append("WEAK_RECOMMENDATION")

    # Rocket: momentum confirmation (MACD vs signal line)
    rocket = False
    if sig_side == "BUY":
        rocket = macd > macd_sig
    elif sig_side == "SELL":
        rocket = macd < macd_sig
    else:
        rocket = False

    if not rocket and sig_side in ("BUY", "SELL"):
        why_not.append("NO_ROCKET_CONFIRM")

    # IDLE-by-default on any uncertainty
    if not (anchor1 and anchor2 and rocket):
        return {
            "name": "proposal_2a1r",
            "symbol": sym,
            "action": "IDLE",
            "confidence": 0.0,
            "why": "IDLE-by-default: conditions not met",
            "why_not": why_not,
            "ts_ms": ts,
            "inputs": {
                "sig_side": sig_side,
                "sig_strength": sig_strength,
                "reco_side": reco_side,
                "reco_strength": reco_strength,
                "rsi": rsi,
                "macd": macd,
                "macd_signal": macd_sig,
            },
        }

    # Deterministic confidence: combine strengths (clamped)
    conf = (max(0.0, min(1.0, sig_strength)) + max(0.0, min(1.0, reco_strength))) / 2.0
    conf = max(0.0, min(1.0, conf))

    return {
        "name": "proposal_2a1r",
        "symbol": sym,
        "action": sig_side,  # BUY/SELL (proposal only)
        "confidence": conf,
        "why": "2 anchors confirmed + rocket momentum",
        "why_not": [],
        "ts_ms": ts,
        "inputs": {
            "sig_side": sig_side,
            "sig_strength": sig_strength,
            "reco_side": reco_side,
            "reco_strength": reco_strength,
            "rsi": rsi,
            "macd": macd,
            "macd_signal": macd_sig,
        },
    }
