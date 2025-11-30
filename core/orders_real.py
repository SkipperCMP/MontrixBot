# core/orders_real.py — ensures .env is loaded and sends REAL orders
from __future__ import annotations

import os
import math
from typing import Optional

# Load .env if present
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(), override=False)
except Exception:
    # .env is optional; REAL mode will still fail later if keys are missing
    pass

from tools.safe_lock import is_safe_on, require_unlock
from tools import binance_time_sync as tsync
from core.binance_filters import hard_round_and_validate

try:
    from binance.client import Client
    from binance.exceptions import BinanceAPIException
except Exception:  # pragma: no cover - python-binance not installed
    Client = None
    BinanceAPIException = Exception


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
        pass


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
