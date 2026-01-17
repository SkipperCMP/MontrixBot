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

def read_equity_history(*, max_points: Optional[int] = None) -> list[tuple[float, float]]:
    """Read runtime/equity_history.csv in a read-only manner.

    Returns list of (ts, equity), sorted as in file.
    - If file is missing or invalid -> []
    - If max_points is set -> keep only last N points
    """
    try:
        if not EQUITY_HISTORY_FILE.exists():
            return []
    except Exception:
        return []

    out: list[tuple[float, float]] = []
    try:
        with EQUITY_HISTORY_FILE.open("r", newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                try:
                    ts = float(row.get("ts") or 0.0)
                    eq = float(row.get("equity") or 0.0)
                    if ts > 0:
                        out.append((ts, eq))
                except Exception:
                    continue
    except Exception:
        return []

    if max_points is not None:
        try:
            n = int(max_points)
            if n > 0 and len(out) > n:
                out = out[-n:]
        except Exception:
            pass
    return out
