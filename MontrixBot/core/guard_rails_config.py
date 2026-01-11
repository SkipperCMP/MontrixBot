from dataclasses import dataclass
import os
from typing import List, Optional


def _csv(env: str) -> Optional[List[str]]:
    v = os.getenv(env)
    if not v:
        return None
    return [x.strip() for x in v.split(",") if x.strip()]


def _float_env(k: str) -> Optional[float]:
    v = os.getenv(k)
    if v is None or v == "":
        return None
    return float(v)


def _int_env(k: str) -> Optional[int]:
    v = os.getenv(k)
    if v is None or v == "":
        return None
    return int(v)


@dataclass(frozen=True)
class GuardRailsConfig:
    enabled: bool

    allowed_order_types: List[str]

    symbol_allow: Optional[List[str]]
    symbol_deny: Optional[List[str]]

    max_qty: Optional[float]
    max_notional: Optional[float]

    max_orders_60s: Optional[int]
    max_orders_10m: Optional[int]
    max_orders_24h: Optional[int]

    symbol_cooldown_s: Optional[int]

    @classmethod
    def from_env(cls) -> "GuardRailsConfig":
        return cls(
            enabled=os.getenv("REAL_GUARD_RAILS") == "1",

            allowed_order_types=_csv("REAL_ALLOWED_ORDER_TYPES") or ["MARKET", "LIMIT"],

            symbol_allow=_csv("REAL_SYMBOL_ALLOW"),
            symbol_deny=_csv("REAL_SYMBOL_DENY"),

            max_qty=_float_env("REAL_MAX_QTY"),
            max_notional=_float_env("REAL_MAX_NOTIONAL"),

            max_orders_60s=_int_env("REAL_MAX_ORDERS_60S"),
            max_orders_10m=_int_env("REAL_MAX_ORDERS_10M"),
            max_orders_24h=_int_env("REAL_MAX_ORDERS_24H"),

            symbol_cooldown_s=_int_env("REAL_SYMBOL_COOLDOWN_S"),
        )
