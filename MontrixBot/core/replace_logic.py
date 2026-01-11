from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ReplaceDecision:
    """Простое решение ReplaceLogic для 1.2.1.

    action:
        "none"  — ничего не делаем (HOLD)
        "buy"   — открыть / усилить позицию
        "close" — закрыть позицию

    side:
        Направление исходного сигнала ("BUY" / "SELL" / "HOLD").

    confidence:
        Уверенность (0.0–1.0+) на основе силы сигнала/рекомендации.

    reason:
        Краткое текстовое объяснение.
    """

    action: str
    side: str
    confidence: float
    reason: str


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def decide_from_signal_and_reco(
    signal: Dict[str, Any],
    recommendation: Optional[Dict[str, Any]] = None,
) -> ReplaceDecision:
    """Минимальная версия ReplaceLogic 1.2.1.

    На вход:
      - signal: dict из core.signals.SimpleSignal.as_dict()
      - recommendation: dict из advisor.compute_recommendation(...) или None

    На выход:
      - ReplaceDecision с action / side / confidence / reason.

    Важно: пока НЕ трогаем ни executor, ни autosim.
    Это лишь аналитический слой поверх сигналов.
    """

    side = str(signal.get("side", "HOLD")).upper()
    strength = _safe_float(signal.get("strength", 0.0), 0.0)

    reco_side = "HOLD"
    reco_strength = 0.0
    if isinstance(recommendation, dict):
        reco_side = str(recommendation.get("side", "HOLD")).upper()
        reco_strength = _safe_float(recommendation.get("strength", 0.0), 0.0)

    # --- базовая логика 1.2.1 ---
    action = "none"
    reasons = []

    if side == "BUY":
        # BUY-сигнал + BUY/FLAT-рекомендация → открыть/усилить позицию
        if reco_side in ("BUY", "HOLD"):
            action = "buy"
            if reco_side == "BUY":
                reasons.append("BUY signal confirmed by advisor")
            else:
                reasons.append("BUY signal (no strong SELL recommendation)")
        else:
            reasons.append("BUY signal but advisor is SELL — HOLD")

    elif side == "SELL":
        # SELL-сигнал + SELL-рекомендация → закрыть позицию
        if reco_side == "SELL":
            action = "close"
            reasons.append("SELL signal confirmed by advisor")
        else:
            reasons.append("SELL signal but advisor is not SELL — HOLD")

    else:
        reasons.append("No strong BUY/SELL signal — HOLD")

    if action == "none":
        reasons.append("No replace action selected")

    confidence = max(strength, reco_strength)
    reason_text = "; ".join(r for r in reasons if r)

    return ReplaceDecision(
        action=action,
        side=side,
        confidence=confidence,
        reason=reason_text,
    )


__all__ = ["ReplaceDecision", "decide_from_signal_and_reco"]
