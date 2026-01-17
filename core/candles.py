from __future__ import annotations

"""core/candles.py

Read-only helpers for building OHLC candles from tick stream rows.

Design goals:
- Pure / deterministic: no file I/O, no network, no runtime writes.
- Best-effort parsing: ignores malformed ticks.
- Stable contract for UI Chart v2 adapter.

Tick row schema (compatible with tools/ticks_*_stream.py):
  {"symbol": "BTCUSDT", "price": 1.23, "bid": 1.23, "ask": 1.23, "ts": 1700000000000}

We also accept:
- price under keys: price / p / close
- timestamp under keys: ts / t / time / timestamp  (milliseconds since epoch)
"""

from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class Candle:
    ts_open_ms: int
    o: float
    h: float
    l: float
    c: float
    n: int  # ticks count in candle

    def as_dict(self) -> dict:
        return {
            "ts_open_ms": int(self.ts_open_ms),
            "o": float(self.o),
            "h": float(self.h),
            "l": float(self.l),
            "c": float(self.c),
            "n": int(self.n),
        }


def _pick_ts_ms(row: dict) -> Optional[int]:
    for k in ("ts", "t", "time", "timestamp"):
        v = row.get(k)
        if v is None:
            continue
        try:
            # support string / float / int
            return int(float(v))
        except Exception:
            continue
    return None


def _pick_price(row: dict) -> Optional[float]:
    for k in ("price", "p", "close"):
        v = row.get(k)
        if v is None:
            continue
        try:
            return float(v)
        except Exception:
            continue
    return None


def build_ohlc_from_ticks(
    ticks: Iterable[dict],
    *,
    timeframe_ms: int,
    max_candles: int = 300,
) -> Tuple[List[Candle], Optional[int]]:
    """Aggregate ticks into OHLC candles.

    Returns:
      (candles, last_ts_ms)

    Notes:
    - timeframe_ms must be > 0
    - candles are ordered by ts_open_ms ascending
    - last_ts_ms is the last parsed tick ts (or None if no ticks)
    """
    tf = int(timeframe_ms or 0)
    if tf <= 0:
        return ([], None)

    # best-effort: keep only ticks with (ts, price)
    parsed: List[Tuple[int, float]] = []
    last_ts: Optional[int] = None
    for row in ticks:
        if not isinstance(row, dict):
            continue
        ts = _pick_ts_ms(row)
        px = _pick_price(row)
        if ts is None or px is None:
            continue
        parsed.append((ts, px))
        last_ts = ts

    if not parsed:
        return ([], None)

    # ensure chronological
    parsed.sort(key=lambda x: x[0])

    candles: List[Candle] = []
    cur_open: Optional[int] = None
    o = h = l = c = None  # type: ignore[assignment]
    n = 0

    def _flush():
        nonlocal cur_open, o, h, l, c, n
        if cur_open is None or n <= 0:
            return
        candles.append(Candle(ts_open_ms=cur_open, o=o, h=h, l=l, c=c, n=n))
        cur_open = None
        n = 0

    for ts, px in parsed:
        bucket = (ts // tf) * tf
        if cur_open is None:
            cur_open = bucket
            o = h = l = c = float(px)
            n = 1
            continue

        if bucket != cur_open:
            _flush()
            cur_open = bucket
            o = h = l = c = float(px)
            n = 1
            continue

        # same candle
        c = float(px)
        if px > h:
            h = float(px)
        if px < l:
            l = float(px)
        n += 1

    _flush()

    if max_candles and len(candles) > int(max_candles):
        candles = candles[-int(max_candles) :]

    return (candles, last_ts)
