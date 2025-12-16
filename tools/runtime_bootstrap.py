from __future__ import annotations


def ensure_ticks_bootstrap(symbol: str, max_points: int = 300, interval: str = "1m", min_points: int = 50) -> int:
    """
    Ticks bootstrap hook used by UI/app_step9.py.

    Return value is best-effort count of loaded points.
    Current implementation is a safe stub (no network / no IO).
    """
    return 0
