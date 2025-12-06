#!/usr/bin/env python3
"""
autosim_step1_2_9.py — долгий SIM / StressTest для MontrixBot 1.2-pre2

Цели:
- прогнать StateEngine через N тиков синтетической цены;
- убедиться, что:
    * upsert_ticker отрабатывает без исключений;
    * ipc_ticks поток пишется;
    * TPSL-хук (если будет подключён) не роняет цикл;
- зафиксировать метрики в runtime/autosim_1_2_9_summary.json.

Запуск (из корня проекта):
    python scripts/autosim_step1_2_9.py
    python scripts/autosim_step1_2_9.py --ticks 20000 --interval 0.001
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Dict, Any

# --- bootstrap: корень проекта на sys.path ---
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Теперь доступны core / tools / ui и т.п.
from core.state_engine import StateEngine  # type: ignore[import]
from tools import ipc_ticks  # type: ignore[import]


RUNTIME_DIR = ROOT / "runtime"
SUMMARY_FILE = RUNTIME_DIR / "autosim_1_2_9_summary.json"


def run_autosim(
    symbol: str = "ADAUSDT",
    ticks: int = 5000,
    base_price: float = 100.0,
    vol: float = 0.003,
    interval: float = 0.0,
) -> Dict[str, Any]:
    """
    Основной цикл автосима.

    Параметры:
    - symbol   — торгуемый символ;
    - ticks    — количество тиков в прогоне;
    - base_price — стартовая цена;
    - vol      — амплитуда случайного шага (random walk);
    - interval — задержка между тиками (секунды).
    """
    os.makedirs(RUNTIME_DIR, exist_ok=True)

    # Чистим тик-стрим, чтобы не разъезжался файл
    try:
        ipc_ticks.reset_stream()
    except Exception:
        # сбой сброса не должен ломать тест
        pass

    se = StateEngine(enable_tpsl=True)

    price = float(base_price)
    errors = 0
    ticks_ok = 0

    t_start = time.time()

    print(
        f"[AUTOSIM] start symbol={symbol} ticks={ticks} base={base_price} "
        f"vol={vol} interval={interval}"
    )

    for i in range(ticks):
        # простая random-walk модель
        step = random.uniform(-vol, vol)
        price *= (1.0 + step)

        bid = price - 0.01
        ask = price + 0.01
        ts = time.time()

        try:
            se.upsert_ticker(symbol, last=price, bid=bid, ask=ask, ts=ts)
            ticks_ok += 1
        except Exception as e:
            errors += 1
            # Логируем, но продолжаем цикл
            print(f"[AUTOSIM][ERR] tick={i} error={e!r}", file=sys.stderr)

        # лёгкий прогресс-лог
        if (i + 1) % max(1, ticks // 10) == 0:
            print(f"[AUTOSIM] progress {i+1}/{ticks} ticks, price={price:.4f}")

        if interval > 0:
            time.sleep(interval)

    t_end = time.time()
    dur = max(1e-6, t_end - t_start)
    tps = ticks_ok / dur

    summary: Dict[str, Any] = {
        "symbol": symbol,
        "ticks_requested": ticks,
        "ticks_ok": ticks_ok,
        "errors": errors,
        "duration_sec": dur,
        "ticks_per_sec": tps,
        "last_price": price,
        "ts_start": t_start,
        "ts_end": t_end,
        "version": "1.2-pre2_STEP1.2.9",
    }

    print("[AUTOSIM] summary:", summary)

    try:
        with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"[AUTOSIM] summary saved to {SUMMARY_FILE}")
    except Exception as e:
        print(f"[AUTOSIM][WARN] failed to save summary: {e!r}", file=sys.stderr)

    return summary


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="MontrixBot Autosim / StressTest (1.2.9)")
    p.add_argument("--symbol", default="ADAUSDT", help="symbol (default: ADAUSDT)")
    p.add_argument(
        "--ticks", type=int, default=5000, help="number of ticks to simulate"
    )
    p.add_argument(
        "--interval",
        type=float,
        default=0.0,
        help="sleep between ticks in seconds (default 0.0)",
    )
    p.add_argument(
        "--base-price",
        type=float,
        default=100.0,
        help="starting price for synthetic series",
    )
    p.add_argument(
        "--vol",
        type=float,
        default=0.003,
        help="amplitude of random step (default 0.003 = 0.3%%)",
    )
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    summary = run_autosim(
        symbol=args.symbol,
        ticks=args.ticks,
        base_price=args.base_price,
        vol=args.vol,
        interval=args.interval,
    )
    ok = summary.get("errors", 0) == 0
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
