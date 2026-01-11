from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Optional, Any


# runtime/equity_history.csv (append-only)
ROOT_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = ROOT_DIR / "runtime"
EQUITY_HISTORY_FILE = RUNTIME_DIR / "equity_history.csv"


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def append_equity_point(
    *,
    ts: Optional[float] = None,
    equity: Any = None,
    mode: str = "SIM",
    source: str = "UI",
) -> None:
    """
    Append one row into runtime/equity_history.csv.

    Columns: ts, equity, mode, source
    """
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    _ts = float(ts) if ts is not None else time.time()
    _equity = _safe_float(equity, default=0.0)
    _mode = (mode or "SIM").upper()
    _source = str(source or "UI")

    file_exists = EQUITY_HISTORY_FILE.exists()

    with EQUITY_HISTORY_FILE.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not file_exists:
            w.writerow(["ts", "equity", "mode", "source"])
        w.writerow([f"{_ts:.3f}", f"{_equity:.8f}", _mode, _source])
