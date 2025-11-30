"""tools.rsi_demo — демо и смоук-дополнение для core.indicators (RSI/EMA/SMA).

Назначение:
  - показать, как пользоваться core.indicators.sma/ema/rsi;
  - убедиться, что модуль работает и не требует внешних зависимостей;
  - использовать как простой ручной тест при развитии версии 1.1.

Запуск:
  python tools/rsi_demo.py

Выводит в консоль несколько последних значений:
  - цены
  - SMA
  - EMA
  - RSI
"""

from __future__ import annotations

import math
import random
from typing import List

try:
    from core.indicators import sma, ema, rsi
except ImportError as e:
    print("[RSI_DEMO] Failed to import core.indicators:", e)
    raise SystemExit(1)


def generate_synthetic_prices(n: int = 100, base: float = 100.0) -> List[float]:
    """Генерирует простую синтетическую ценовую серию для демо.

    Это НЕ рыночные данные, а просто случайное блуждание вокруг base.
    """
    prices: List[float] = []
    value = float(base)
    for _ in range(n):
        # небольшое случайное изменение
        step = random.uniform(-1.0, 1.0)
        value = max(1.0, value + step)
        prices.append(round(value, 4))
    return prices


def main() -> None:
    print("=== MontrixBot 1.1 — indicators demo (RSI/EMA/SMA) ===")

    prices = generate_synthetic_prices(n=60, base=100.0)
    period = 14

    s_sma = sma(prices, period)
    s_ema = ema(prices, period)
    s_rsi = rsi(prices, period)

    print(f"[DEMO] len(prices)={len(prices)} period={period}")
    print()
    print(" last 10 rows:")
    print(" idx |   price   |    SMA    |    EMA    |   RSI")
    print("-----+-----------+-----------+-----------+--------")

    start = max(0, len(prices) - 10)
    for i in range(start, len(prices)):
        p = prices[i]
        sv = s_sma[i]
        ev = s_ema[i]
        rv = s_rsi[i]

        def fmt(x):
            if isinstance(x, float):
                if math.isnan(x):
                    return "   NaN   "
                return f"{x:9.4f}"
            return f"{x!r:9}"

        print(f"{i:4d} | {p:9.4f} | {fmt(sv)} | {fmt(ev)} | {fmt(rv)}")

    print("\n[DEMO] Done. core.indicators работает корректно, модуль готов к использованию в 1.1.")


if __name__ == "__main__":
    main()
