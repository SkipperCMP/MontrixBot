# -*- coding: utf-8 -*-
"""
ticks_streamer_fake.py - FAKE ticks generator for MontrixBot LIVE Chart (1.1)

This script generates synthetic ticks and writes them to runtime/ticks_stream.jsonl.
It is used only for testing LIVE Chart without touching Binance.

Run:
  python tools/ticks_streamer_fake.py
  python tools/ticks_streamer_fake.py --symbol BTCUSDT --base 60000 --step 20 --interval 0.5
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path


def build_args():
    parser = argparse.ArgumentParser(description="MontrixBot FAKE ticks streamer")
    parser.add_argument("--symbol", default="ADAUSDT", help="Symbol (default ADAUSDT)")
    parser.add_argument("--base", type=float, default=100.0, help="Initial price (default 100.0)")
    parser.add_argument("--step", type=float, default=0.2, help="Max random delta per tick (default 0.2)")
    parser.add_argument("--spread", type=float, default=0.05, help="Bid/ask spread (default 0.05)")
    parser.add_argument("--interval", type=float, default=0.3, help="Tick interval seconds (default 0.3)")
    parser.add_argument("--max-ticks", type=int, default=0, help="Max ticks (0 = infinite)")
    return parser.parse_args()


def get_paths():
    root = Path(__file__).resolve().parent.parent
    runtime = root / "runtime"
    runtime.mkdir(exist_ok=True)
    stream_file = runtime / "ticks_stream.jsonl"
    return runtime, stream_file


def main():
    args = build_args()
    runtime, stream_file = get_paths()

    symbol = args.symbol.upper()
    price = float(args.base)
    step = float(args.step)
    spread = float(args.spread)
    interval = float(args.interval)
    max_ticks = int(args.max_ticks)

    print("[FAKE] MontrixBot ticks streamer started")
    print(f"[FAKE] runtime: {runtime}")
    print(f"[FAKE] stream:  {stream_file}")
    print(f"[FAKE] symbol:  {symbol}")

    ticks_written = 0

    try:
        with stream_file.open("a", encoding="utf-8") as f:
            while True:
                if max_ticks > 0 and ticks_written >= max_ticks:
                    print(f"[FAKE] done: reached max_ticks = {max_ticks}")
                    break

                delta = random.uniform(-step, step)
                price = max(0.0000001, price + delta)

                bid = price - spread / 2
                ask = price + spread / 2

                obj = {
                    "symbol": symbol,
                    "price": round(price, 6),
                    "bid": round(bid, 6),
                    "ask": round(ask, 6),
                    "ts": int(time.time() * 1000),
                }

                line = json.dumps(obj, ensure_ascii=False)
                f.write(line + "\n")
                f.flush()

                print("[FAKE]", line)
                ticks_written += 1

                time.sleep(interval)

    except KeyboardInterrupt:
        print("\n[FAKE] interrupted by user")
    except Exception as e:
        print("[FAKE][ERR]", repr(e))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
