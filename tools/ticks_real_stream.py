# -*- coding: utf-8 -*-
"""
tools/ticks_real_stream.py

REAL market stream writer -> runtime/ticks_stream.jsonl

It uses existing project feeds:
- core/feeds/binance_ws.py (websocket-client) miniTicker array
- core/feeds/binance_poll.py (urllib) 24hr ticker polling

We keep JSONL schema compatible with current UI tick reader:
  {"symbol": "...", "price": 1.23, "bid": 1.23, "ask": 1.23, "ts": 1700000000000}

Note:
miniTicker & 24hr ticker provide last/open (no bid/ask). For UI tick line we set bid=ask=price.
This is still "real market" (real last price), just without spread.
"""

from __future__ import annotations

import argparse
import json
import time
import sys
from pathlib import Path
from typing import List

# --- project root discovery ---
ROOT_DIR = Path(__file__).resolve().parent.parent

# Ensure project root is importable when run as: python tools/xxx.py
# (otherwise sys.path points to "tools", and "core" is not found)
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

RUNTIME_DIR = ROOT_DIR / "runtime"
RUNTIME_DIR.mkdir(exist_ok=True)
TICKS_FILE = RUNTIME_DIR / "ticks_stream.jsonl"

# feeds (already in project)
from core.feeds.binance_ws import BinanceMiniTickerThread
from core.feeds.binance_poll import BinancePollThread


def _now_ms() -> int:
    return int(time.time() * 1000)


def _write_tick(symbol: str, price: float) -> None:
    obj = {
        "symbol": str(symbol).upper(),
        "price": float(price),
        "bid": float(price),   # no bid/ask in miniTicker/24hr => keep UI schema stable
        "ask": float(price),
        "ts": _now_ms(),
    }
    with TICKS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def build_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Write REAL market prices into runtime/ticks_stream.jsonl")
    p.add_argument(
        "--symbols",
        default="ADAUSDT",
        help="Comma-separated symbols, e.g. ADAUSDT,BTCUSDT,ETHUSDT",
    )
    p.add_argument(
        "--mode",
        default="ws",
        choices=["ws", "poll"],
        help="ws = websocket miniTicker (requires websocket-client); poll = REST 24hr polling",
    )
    p.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Polling interval seconds (mode=poll)",
    )
    p.add_argument(
        "--reset",
        action="store_true",
        help="Truncate runtime/ticks_stream.jsonl before streaming",
    )
    return p.parse_args()


def main() -> None:
    args = build_args()
    symbols: List[str] = [s.strip().upper() for s in str(args.symbols).split(",") if s.strip()]
    if not symbols:
        symbols = ["ADAUSDT"]

    if args.reset:
        TICKS_FILE.write_text("", encoding="utf-8")

    print(f"[REAL] writing ticks to {TICKS_FILE}")
    print(f"[REAL] mode={args.mode} symbols={symbols}")

    def on_quote(symbol: str, last_price: float, _pct: float) -> None:
        try:
            _write_tick(symbol, float(last_price))
        except Exception:
            # don't crash the feed thread on IO errors
            return

    if args.mode == "poll":
        t = BinancePollThread(symbols=symbols, on_quote=on_quote, interval_sec=float(args.interval))
        t.start()
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            t.stop()
        return

    # ws mode
    t = BinanceMiniTickerThread(symbols=symbols, on_quote=on_quote, trace=False, insecure_ssl=False)
    t.start()
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        t.stop()


if __name__ == "__main__":
    main()
