# core/orders_real.py — ensures .env is loaded and sends REAL orders
from __future__ import annotations


import os
import math
from typing import Optional

import logging
import time

from core.policy_trace_store import PolicyTraceStore
from core.policy_trace import PolicyDecision
from core.guard_rails import evaluate_guard_rails
from core.guard_rails_config import GuardRailsConfig
from core.guard_rails_state import load_guard_rails_state, save_guard_rails_state_atomic
from core.system_clock import SystemClock

log = logging.getLogger(__name__)
_LOG_THROTTLE = {}

def _log_throttled(key: str, msg: str, *, interval_s: float = 300.0):
    try:
        now = time.time()
        last = _LOG_THROTTLE.get(key, 0.0)
        if now - last < interval_s:
            return
        _LOG_THROTTLE[key] = now
        log.exception(msg)
    except Exception:
        return


# Load .env if present  ← ✔ ВНЕ ФУНКЦИИ
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(), override=False)
except Exception:
    _log_throttled(
        "orders_real.dotenv",
        "orders_real: failed to load .env (optional, continuing)",
        interval_s=600.0,
    )

from tools.safe_lock import is_safe_on, require_unlock
from tools import binance_time_sync as tsync
from core.binance_filters import hard_round_and_validate

try:
    from binance.client import Client
    from binance.exceptions import BinanceAPIException
except Exception:  # pragma: no cover - python-binance not installed
    Client = None
    BinanceAPIException = Exception


def _is_panic_active_best_effort() -> bool:
    """
    Best-effort PANIC check.

    If core.panic_tools is missing, assume PANIC is not active.
    This preserves backward compatibility and avoids false blocks.
    """
    try:
        from core.panic_tools import is_panic_active  # type: ignore
        return bool(is_panic_active())
    except Exception:
        return False


def _load_keys() -> tuple[Optional[str], Optional[str]]:
    ak = os.getenv("API_KEY") or os.getenv("BINANCE_API_KEY")
    sk = os.getenv("API_SECRET") or os.getenv("BINANCE_SECRET")
    return ak, sk


def _ensure_client() -> "Client":
    if Client is None:
        raise RuntimeError("python-binance is not installed")
    ak, sk = _load_keys()
    if not ak or not sk:
        raise RuntimeError(
            "API keys are missing; set API_KEY/API_SECRET or BINANCE_API_KEY/BINANCE_SECRET"
        )
    return Client(ak, sk)


def _preflight_real(safe_code: Optional[str] = None) -> None:
    """Common SAFE/time-sync checks before sending REAL orders."""
    if is_safe_on():
        # SAFE lock must be explicitly unlocked for any REAL order
        if not (safe_code and require_unlock(safe_code)):
            raise PermissionError(
                "SAFE is ON — provide valid unlock code to place REAL orders"
            )
    try:
        # Best-effort clock sync; errors are non-fatal (Binance will still validate recvWindow)
        tsync.sync_time()
    except Exception:
        _log_throttled(
            "orders_real.time_sync",
            "orders_real: time sync failed (best-effort, continuing)",
            interval_s=300.0,
        )



def _apply_filters(
    symbol: str,
    quantity: Optional[float],
    price: Optional[float],
) -> tuple[Optional[float], Optional[float]]:
    """Apply Binance LOT_SIZE / NOTIONAL filters via core.binance_filters.

    Returns (price, quantity) possibly adjusted. If something goes wrong, the
    original values are returned and Binance will perform final validation.
    """
    if quantity is None and price is None:
        return price, quantity

    try:
        # For MARKET orders we may not have a price; use a neutral fallback
        p_for_filters = price if price is not None else 1.0
        rp, rq, ok_notional, sf = hard_round_and_validate(
            symbol, p_for_filters, float(quantity or 0.0)
        )

        # If notional is too small, bump quantity to the minimal value satisfying filters
        if not ok_notional:
            step = sf.step_size or 0.01
            min_qty = sf.min_qty or step
            target = max(min_qty, (sf.min_notional + 1e-8) / max(rp, 1e-12))
            steps = math.ceil(target / step)
            rq = steps * step

        # For MARKET orders we return the rounded price for internal checks,
        # but do not force-send it to Binance (MARKET uses quantity only).
        return (price, rq) if price is not None else (rp, rq)
    except Exception:
        # On any error (no exchange_info.json, parse issues, etc.) fall back to raw values
        return price, quantity


def place_order_real(
    symbol: str,
    side: str,
    type_: str = "MARKET",
    quantity: Optional[float] = None,
    price: Optional[float] = None,
    safe_code: Optional[str] = None,
    **kwargs,
):
    # --- GLOBAL REAL GATE (STEP1.4.8) ---
    from tools.safe_lock import is_safe_on, require_unlock
    from core.runtime_state import load_runtime_state

    # SAFE lock: allow REAL only if SAFE is unlocked with a valid code.
    if is_safe_on() and not (safe_code and require_unlock(str(safe_code))):
        PolicyTraceStore.append(
            policy="REAL_GUARD",
            decision=PolicyDecision.VETO,
            reason_code="SAFE_MODE",
            details={"safe_mode": True, "unlocked": False},
            scope="REAL",
            source="orders_real.place_order_real",
        )
        raise PermissionError("SAFE is ON — provide valid unlock code to place REAL orders")

    # --- MANUAL CONFIRM SURFACE (v2.2.105) ---
    # Any REAL order requires one-time human confirmation token.
    try:
        from core.risky_confirm import RiskyConfirmService
        confirm_token = kwargs.get("confirm_token")
        confirm_actor = (kwargs.get("confirm_actor") or "local").strip()

        if not confirm_token:
            PolicyTraceStore.append(
                policy="REAL_GUARD",
                decision=PolicyDecision.VETO,
                reason_code="REAL_CONFIRM_REQUIRED",
                details={"confirm_actor": confirm_actor},
                scope="REAL",
                source="orders_real.place_order_real",
            )
            raise PermissionError("REAL confirm required — pass confirm token (manual-only surface)")

        ok, cmd_text, msg_code = RiskyConfirmService().confirm(str(confirm_token), actor=confirm_actor)
        if not ok:
            PolicyTraceStore.append(
                policy="REAL_GUARD",
                decision=PolicyDecision.VETO,
                reason_code=f"REAL_CONFIRM_{msg_code}",
                details={"confirm_actor": confirm_actor},
                scope="REAL",
                source="orders_real.place_order_real",
            )
            raise PermissionError(f"REAL confirm rejected: {msg_code}")
    except PermissionError:
        raise
    except Exception:
        # fail-safe: if confirm layer errors, block REAL
        PolicyTraceStore.append(
            policy="REAL_GUARD",
            decision=PolicyDecision.VETO,
            reason_code="REAL_CONFIRM_ERROR",
            details={},
            scope="REAL",
            source="orders_real.place_order_real",
        )
        raise PermissionError("REAL confirm error — blocked (fail-safe)")

    if _is_panic_active_best_effort():
        PolicyTraceStore.append(
            policy="REAL_GUARD",
            decision=PolicyDecision.VETO,
            reason_code="PANIC",
            details={"panic": True},
            scope="REAL",
            source="orders_real.place_order_real",
        )
        raise PermissionError("REAL blocked: PANIC active")

    st = load_runtime_state() or {}
    meta = st.get("meta") or {}

    tg = meta.get("trading_gate")
    if tg != "ALLOW":
        PolicyTraceStore.append(
            policy="REAL_GUARD",
            decision=PolicyDecision.VETO,
            reason_code="TRADING_GATE_DENY",
            details={"trading_gate": tg},
            scope="REAL",
            source="orders_real.place_order_real",
        )
        raise PermissionError("REAL blocked: trading_gate != ALLOW")

    ss = meta.get("strategy_state")
    if ss == "PAUSED":
        # PRODUCT-MODE: "strategy paused" is a risk/logic stop (not a technical stop).
        # Manual REAL must be allowed here (confirmation UX is handled at UI layer).
        PolicyTraceStore.append(
            policy="REAL_GUARD",
            decision=PolicyDecision.ALLOW,
            reason_code="STRATEGY_PAUSED_MANUAL_ALLOWED",
            details={"strategy_state": ss},
            scope="REAL",
            source="orders_real.place_order_real",
        )
        log.warning("REAL allowed while strategy_state=PAUSED (manual override)")
        # Do NOT raise; continue to real order placement.

    # --- Guard Rails (STEP 1.9.D) ---
    cfg = GuardRailsConfig.from_env()
    if cfg.enabled:
        now_ms = SystemClock.now_exchange_ms()

        runtime_dir = PolicyTraceStore._runtime_dir()
        state_path = str(runtime_dir / "guard_rails_state.json")

        state = load_guard_rails_state(state_path)

        # Trim old attempts (keep state bounded)
        state.trim(max_age_ms=24 * 60 * 60 * 1000)

        decision = evaluate_guard_rails(
            cfg=cfg,
            state=state,
            symbol=symbol,
            type_=type_.upper(),
            quantity=float(quantity or 0.0),
            price=float(price) if price is not None else None,
            price_hint=float(kwargs.get("price_hint")) if kwargs.get("price_hint") is not None else None,
            now_ms=now_ms,
        )

        # Record attempt that reached guard rails (counts ALLOW and VETO)
        state.record_attempt(ts_ms=now_ms, symbol=symbol)
        save_guard_rails_state_atomic(state_path, state)

        if decision.decision == "VETO":
            PolicyTraceStore.append(
                policy="REAL_GUARD_RAILS",
                decision=PolicyDecision.VETO,
                reason_code=decision.reason_code,
                details=decision.details,
                scope="REAL",
                source="orders_real.place_order_real",
            )
            raise PermissionError(f"Guard rails veto: {decision.reason_code}")

    # ALLOW (diagnostic only)
    PolicyTraceStore.append(
        policy="REAL_GUARD",
        decision=PolicyDecision.ALLOW,
        reason_code="OK",
        details={"trading_gate": tg, "strategy_state": ss},
        scope="REAL",
        source="orders_real.place_order_real",
    )

    """Place a REAL order using python-binance with SAFE + filter guards.

    This helper performs:
    - SAFE lock / unlock checks
    - optional time sync
    - local LOT_SIZE / NOTIONAL rounding via `core.binance_filters`
    Final validation is still done by Binance (BinanceAPIException is propagated).
    """
    _preflight_real(safe_code=safe_code)
    cli = _ensure_client()

    side_u = side.upper()
    type_u = type_.upper()

    # Apply local filters/rounding before constructing payload
    adj_price, adj_qty = _apply_filters(symbol, quantity, price)

    params = dict(symbol=symbol, side=side_u, type=type_u)
    if adj_qty is not None:
        params["quantity"] = adj_qty
    if adj_price is not None and type_u != "MARKET":
        params["price"] = adj_price
        if type_u == "LIMIT":
            params.setdefault("timeInForce", "GTC")

    # Allow callers to override / extend params (e.g. recvWindow)
    params.update(kwargs)

    return cli.create_order(**params)
