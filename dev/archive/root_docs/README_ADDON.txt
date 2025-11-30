TPSL Price Adapter & Smoke Test Add-on
Date: 2025-11-12 19:54:30 UTC

Назначение
— Гарантирует рабочий источник цены для TPSL в SIM-режиме (runtime/price_cache.py).
— Даёт простой скрипт dev/tpsl_smoke_test.py, который создаёт позицию и двигает цену.

Как применить
1) Распакуйте этот патч в КОРЕНЬ проекта (с заменой).
2) Запустите:  python dev/tpsl_smoke_test.py
   В консоли увидите последовательность Price -> ... и логи TPSL.
3) Если в проекте уже есть свой price-cache/тикер — без проблем, этот модуль не мешает.
   TPSL берёт цену через runtime.price_cache.get_cached_price().
