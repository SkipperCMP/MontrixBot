
from __future__ import annotations

def _safe_float(x) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0

def fmt_price(x: float) -> str:
    v = _safe_float(x)
    try:
        return f"{v:,.2f}".replace(",", " ")
    except Exception:
        return "—"

def fmt_qty(x: float) -> str:
    v = _safe_float(x)
    s = f"{v:,.6f}".replace(",", " ")
    s = s.rstrip("0").rstrip(".")
    return s if s else "0"

def fmt_pnl(x: float) -> str:
    v = _safe_float(x)
    sign = "+" if v > 0 else ("−" if v < 0 else "")
    return f"{sign}{abs(v):.2f}"
