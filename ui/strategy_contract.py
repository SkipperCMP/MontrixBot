# ui/strategy_contract.py
# v2.2.51 — Strategy Contract v1 (read-only scaffolding)
# UI-only: defines the shape of a strategy as an object (no power, no execution).

from __future__ import annotations

import os

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class StrategyContractV1:
    """A strategy is a behavior object without authority.

    This contract is *declarative* and read-only in v2.2.51.
    """

    sid: str
    name: str
    purpose: str
    status: str = "enabled"  # enabled | frozen
    risk_profile: str = "low"  # low | medium | high

    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)

    params: Dict[str, Any] = field(default_factory=dict)
    params_schema: Dict[str, Dict[str, Any]] = field(default_factory=dict)


def get_strategy_contracts_v1() -> List[StrategyContractV1]:
    """Static contracts (read-only).

    Later will be wired to a real registry service, but this version keeps it UI-only.
    """
    return [
        StrategyContractV1(
            sid="trend_pulse",
            name="Trend Pulse",
            purpose="Следование тренду (консервативно).",
            status="enabled",
            risk_profile="low",
            inputs=["price", "rsi", "macd"],
            outputs=["recommendation", "confidence"],
            params={
                "timeframe": "1m",
                "min_confidence": 0.55,
            },
            params_schema={
                "timeframe": {"type": "str", "default": "1m", "desc": "Таймфрейм наблюдения."},
                "min_confidence": {"type": "float", "default": 0.55, "desc": "Минимальная уверенность для рекомендации."},
            },
        ),
        StrategyContractV1(
            sid="mean_revert",
            name="Mean Revert",
            purpose="Возврат к среднему (контртренд с фильтрами).",
            status="frozen",
            risk_profile="medium",
            inputs=["price", "rsi"],
            outputs=["recommendation", "confidence"],
            params={
                "timeframe": "1m",
                "rsi_low": 30,
                "rsi_high": 70,
            },
            params_schema={
                "timeframe": {"type": "str", "default": "1m", "desc": "Таймфрейм наблюдения."},
                "rsi_low": {"type": "int", "default": 30, "desc": "RSI порог перепроданности."},
                "rsi_high": {"type": "int", "default": 70, "desc": "RSI порог перекупленности."},
            },
        ),
        StrategyContractV1(
            sid="breakout_guard",
            name="Breakout Guard",
            purpose="Пробой уровней (с защитой от ложных пробоев).",
            status="enabled",
            risk_profile="medium",
            inputs=["price", "volume"],
            outputs=["recommendation", "confidence"],
            params={
                "timeframe": "1m",
                "confirm_bars": 2,
            },
            params_schema={
                "timeframe": {"type": "str", "default": "1m", "desc": "Таймфрейм наблюдения."},
                "confirm_bars": {"type": "int", "default": 2, "desc": "Сколько баров подтверждения пробоя."},
            },
        ),
    ]


# --------------------------------------------------------------------------- UI tuning (read-only)

# Throttle for Strategy Activity Badge / Registry tree updates.
# Can be overridden via env var MONTRIX_UI_ACTIVITY_THROTTLE_SEC (float seconds).
UI_ACTIVITY_THROTTLE_SEC_DEFAULT: float = 1.0


def get_ui_activity_throttle_sec() -> float:
    try:
        v = os.getenv("MONTRIX_UI_ACTIVITY_THROTTLE_SEC", "").strip()
        if v:
            return max(0.0, float(v))
    except Exception:
        pass
    return UI_ACTIVITY_THROTTLE_SEC_DEFAULT
