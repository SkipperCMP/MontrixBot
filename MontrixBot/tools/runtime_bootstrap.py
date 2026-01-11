from __future__ import annotations


def ensure_ticks_bootstrap(symbol: str, max_points: int = 300, interval: str = "1m", min_points: int = 50) -> int:
    """
    Ticks bootstrap hook used by canonical UI (ui/main_app.py).

    Return value is best-effort count of loaded points.
    Current implementation is a safe stub (no network / no IO).
    """
    return 0
