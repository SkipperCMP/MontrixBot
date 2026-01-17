# -*- coding: utf-8 -*-
"""
tools/ticks_book_stream.py

REAL bid/ask writer -> runtime/ticks_stream.jsonl
Source: Binance Spot <symbol>@bookTicker via core/feeds/binance_book_ws.py

JSONL schema (UI compatible):
  {"symbol": "...", "price": 1.23, "bid": 1.22, "ask": 1.24, "ts": 1700000000000}
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

# --- project root discovery ---
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

RUNTIME_DIR = ROOT_DIR / "runtime"
RUNTIME_DIR.mkdir(exist_ok=True)
TICKS_FILE = RUNTIME_DIR / "ticks_stream.jsonl"

from core.feeds.binance_book_ws import BinanceBookTickerThread


def _now_ms() -> int:
    return int(time.time() * 1000)


def _q(x: float) -> float:
    # Remove float noise without "market logic" assumptions
    return float(round(float(x), 8))


def _write_tick(symbol: str, bid: float, ask: float) -> None:
    b = _q(bid)
    a = _q(ask)
    price = _q((b + a) / 2.0) if (b > 0 and a > 0) else _q(b or a or 0.0)
    obj = {
        "symbol": str(symbol).upper(),
        "price": price,
        "bid": b,
        "ask": a,
        "ts": _now_ms(),
    }
    with TICKS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def build_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Write REAL bid/ask into runtime/ticks_stream.jsonl")
    p.add_argument("--symbols", default="ADAUSDT", help="Comma-separated symbols, e.g. ADAUSDT,BTCUSDT,ETHUSDT")
    p.add_argument("--reset", action="store_true", help="Truncate runtime/ticks_stream.jsonl before streaming")
    p.add_argument(
        "--min-ms",
        type=int,
        default=150,
        help="Minimum milliseconds between writes per symbol (even if values change). Default: 150",
    )
    p.add_argument("--trace", action="store_true", help="Enable websocket-client trace")
    p.add_argument("--insecure-ssl", action="store_true", help="Disable SSL cert verification (debug only)")
    return p.parse_args()


def main() -> None:
    args = build_args()
    symbols: List[str] = [s.strip().upper() for s in str(args.symbols).split(",") if s.strip()]
    if not symbols:
        symbols = ["ADAUSDT"]

    if args.reset:
        TICKS_FILE.write_text("", encoding="utf-8")

    print(f"[BOOK] writing ticks to {TICKS_FILE}")
    print(f"[BOOK] symbols={symbols}")
    last_px: Dict[str, Tuple[float, float]] = {}
    last_ts: Dict[str, int] = {}
    min_ms: int = int(args.min_ms)


    def on_book(symbol: str, bid: float, ask: float, bid_qty: float, ask_qty: float) -> None:
        # qty пока не пишем в jsonl — сохраняем контракт UI (price/bid/ask/ts)
        try:
            s = str(symbol).upper()
            b = float(round(float(bid), 8))
            a = float(round(float(ask), 8))

            # dedup: skip exact repeats
            prev = last_px.get(s)
            now_ms = _now_ms()
            prev_ts = last_ts.get(s, 0)

            if prev is not None and prev[0] == b and prev[1] == a:
                # exact same bid/ask -> skip
                return

            # throttle: don't write too frequently even if changing
            if (now_ms - prev_ts) < min_ms:
                return

            _write_tick(s, b, a)
            last_px[s] = (b, a)
            last_ts[s] = now_ms
        except Exception:
            return

    t = BinanceBookTickerThread(
        symbols=symbols,
        on_book=on_book,
        trace=bool(args.trace),
        insecure_ssl=bool(args.insecure_ssl),
    )
    t.start()

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        t.stop()


if __name__ == "__main__":
    main()
