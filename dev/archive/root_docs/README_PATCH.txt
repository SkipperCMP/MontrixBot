MontrixBot 1.0.1+ — TPSL-autoloop (Step 1) — INTEGRATED
Date: 2025-11-12 19:52:35 UTC

Что сделано
- Найден/подключён источник настроек `runtime/settings.json`; добавлен блок `tpsl_autoloop`.
- Добавлены ядро автопетли `core/tpsl_autoloop.py` и раннер `runtime/tpsl_loop.py`.
- Интегрирован хук `start_tpsl_if_enabled()` в main.py (если не был).
- Расширен/добавлен `core/position_manager.py` (методы update_tp/sl, update_max_price).
- Добавлен `runtime/state_manager.py` (если в проекте отсутствовал).
- Опционально: `telegram/commands.py` с командами /autoloop, /update_tp, /update_sl, /tpsl.

Как применить
- Распаковать архив в КОРЕНЬ проекта с заменой файлов (patch-only).
- Убедиться, что ваш источник цен доступен из `get_price(symbol)`:
  • Если есть `runtime/price_cache.get_cached_price` — всё готово.
  • Иначе адаптируйте функцию в main.py: замените логику на ваш SHARED/EventBus.

Smoke-test
1) Стартуйте бота в SIM. В консоли увидите: "TPSL loop started (interval=5s)".
2) Добавьте позицию (через ваш код или напрямую в state) и подвигайте цену — TP должен подтягиваться.
3) Через Telegram выполните /autoloop off — петля мягко остановится в течение ~интервала.
