MontrixBot 1.0.1 — TPSL-autoloop FULL (bundle)
Date: 2025-11-12 20:10:08 UTC

Включено:
- TPSL Core + Runner + SAFE-lock
- GUI: бейдж TPSL (тёмная тема, зелёный ON / красный OFF), PositionPanel обновлён
- Overlays: Matplotlib линии ENTRY/TP/SL (ui/plot_overlays.py)
- runtime: settings.json с tpsl_autoloop, atomic state_manager
- price_adapter: runtime/price_cache.py (SIM)
- dev: tpsl_smoke_test.py с path-shim
- __init__.py для всех пакетов

Интеграция:
1) Распаковать архив в корень проекта (замена файлов).
2) Если у тебя уже есть собственные аналоги модулей — объедини изменения вручную, ориентируясь на этот пакет.
3) Запуск теста:  python dev/tpsl_smoke_test.py

Подключение бейджа TPSL:
- Импортируй PositionPanel и/или TpslStatusBadge в твой UI.
- Для статуса используй функцию, читающую enabled из runtime/settings.json.
