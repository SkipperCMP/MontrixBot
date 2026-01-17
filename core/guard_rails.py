from dataclasses import dataclass
from typing import Literal, Optional

from core.guard_rails_config import GuardRailsConfig
from core.guard_rails_state import GuardRailsState


@dataclass(frozen=True)
class GuardRailsDecision:
    decision: Literal["ALLOW", "VETO"]
    reason_code: str
    details: dict


def _count_attempts_window(attempts: list[dict], *, now_ms: int, window_s: int) -> int:
    if window_s <= 0:
        return 0
    cutoff = int(now_ms) - int(window_s) * 1000
    c = 0
    for a in attempts:
        try:
            ts = int(a.get("ts_ms", 0))
        except Exception:
            ts = 0
        if ts >= cutoff:
            c += 1
    return c


def evaluate_guard_rails(
    *,
    cfg: GuardRailsConfig,
    state: GuardRailsState,
    symbol: str,
    type_: str,
    quantity: float,
    price: Optional[float],
    price_hint: Optional[float],
    now_ms: int,
) -> GuardRailsDecision:
    if not cfg.enabled:
        return GuardRailsDecision("ALLOW", "GR_DISABLED", {"enabled": False})

    # --- Basic allowlists/denylists ---
    if type_ not in cfg.allowed_order_types:
        return GuardRailsDecision(
            "VETO",
            "GR_ORDER_TYPE_NOT_ALLOWED",
            {"type": type_, "allowed": cfg.allowed_order_types},
        )

    if cfg.symbol_allow and symbol not in cfg.symbol_allow:
        return GuardRailsDecision(
            "VETO",
            "GR_SYMBOL_NOT_ALLOWED",
            {"symbol": symbol, "allow": cfg.symbol_allow, "deny": cfg.symbol_deny},
        )

    if cfg.symbol_deny and symbol in cfg.symbol_deny:
        return GuardRailsDecision(
            "VETO",
            "GR_SYMBOL_NOT_ALLOWED",
            {"symbol": symbol, "allow": cfg.symbol_allow, "deny": cfg.symbol_deny},
        )

    # --- Numeric sanity ---
    if quantity <= 0:
        return GuardRailsDecision(
            "VETO",
            "GR_INVALID_NUMERIC",
            {"quantity": quantity},
        )

    # --- Max qty (per order) ---
    if cfg.max_qty is not None and quantity > cfg.max_qty:
        return GuardRailsDecision(
            "VETO",
            "GR_MAX_QTY_EXCEEDED",
            {"quantity": quantity, "max_qty": cfg.max_qty},
        )

    # --- Max notional (per order) ---
    if cfg.max_notional is not None:
        if type_ == "MARKET":
            if price_hint is None:
                return GuardRailsDecision(
                    "VETO",
                    "GR_PRICE_REQUIRED_FOR_NOTIONAL",
                    {"max_notional": cfg.max_notional},
                )
            notional = float(price_hint) * float(quantity)
            src = "PRICE_HINT"
        else:
            if price is None or price <= 0:
                return GuardRailsDecision(
                    "VETO",
                    "GR_INVALID_NUMERIC",
                    {"price": price},
                )
            notional = float(price) * float(quantity)
            src = "LIMIT_PRICE"

        if notional > cfg.max_notional:
            return GuardRailsDecision(
                "VETO",
                "GR_MAX_NOTIONAL_EXCEEDED",
                {
                    "notional": notional,
                    "max_notional": cfg.max_notional,
                    "price_source": src,
                },
            )

    # --- Cooldown (per symbol) ---
    if cfg.symbol_cooldown_s is not None and cfg.symbol_cooldown_s > 0:
        last_ms = state.last_by_symbol.get(symbol)
        if last_ms is not None:
            dt = int(now_ms) - int(last_ms)
            cd_ms = int(cfg.symbol_cooldown_s) * 1000
            if dt < cd_ms:
                return GuardRailsDecision(
                    "VETO",
                    "GR_SYMBOL_COOLDOWN_ACTIVE",
                    {
                        "symbol": symbol,
                        "cooldown_s": int(cfg.symbol_cooldown_s),
                        "since_ms": int(last_ms),
                        "now_ms": int(now_ms),
                    },
                )

    # --- Rate limits (attempts) ---
    # IMPORTANT: state.attempts does NOT include the current attempt yet.
    # We count "+1" for the current call that reached guard rails.
    if cfg.max_orders_60s is not None and cfg.max_orders_60s >= 0:
        c = _count_attempts_window(state.attempts, now_ms=int(now_ms), window_s=60) + 1
        if c > int(cfg.max_orders_60s):
            return GuardRailsDecision(
                "VETO",
                "GR_RATE_LIMIT_EXCEEDED",
                {"window_s": 60, "count": c, "max": int(cfg.max_orders_60s)},
            )

    if cfg.max_orders_10m is not None and cfg.max_orders_10m >= 0:
        c = _count_attempts_window(state.attempts, now_ms=int(now_ms), window_s=600) + 1
        if c > int(cfg.max_orders_10m):
            return GuardRailsDecision(
                "VETO",
                "GR_RATE_LIMIT_EXCEEDED",
                {"window_s": 600, "count": c, "max": int(cfg.max_orders_10m)},
            )

    if cfg.max_orders_24h is not None and cfg.max_orders_24h >= 0:
        c = _count_attempts_window(state.attempts, now_ms=int(now_ms), window_s=86400) + 1
        if c > int(cfg.max_orders_24h):
            return GuardRailsDecision(
                "VETO",
                "GR_RATE_LIMIT_EXCEEDED",
                {"window_s": 86400, "count": c, "max": int(cfg.max_orders_24h)},
            )

    return GuardRailsDecision("ALLOW", "GR_OK", {"enabled": True})
