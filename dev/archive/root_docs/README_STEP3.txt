MontrixBot 1.0.1 — Step 3: Dynamic trailing + GUI controls (FLAT)
Date: 2025-11-12 20:29:33 UTC

Что входит:
- core/tpsl_autoloop.py — режимы 'static'/'dynamic' с оценкой волатильности.
- runtime/tpsl_loop.py — подключение dynamic config и провайдера волатильности.
- runtime/price_cache.py — кольцевой буфер цен и функции get_window_extrema().
- runtime/settings.json — новые параметры (mode, dynamic:*).
- ui/tpsl_controls.py — мини-панель настроек TPSL в верхней панели.
- app.py (пояснение): вставьте блок injection в верхнюю панель, если не подхватится автоматически.

Как применить:
1) Распаковать в корень проекта с заменой.
2) Если панель не появилась автоматически в верхнем баре — откройте ваш ui/app.py и вставьте блок 'TPSL controls injection' в место, где создаётся верхняя панель (top/toolbar/root).

Быстрая проверка:
- Измените 'mode' и проценты через панель, нажмите 'Apply' — значения обновятся в runtime/settings.json.
- Запустите smoke-тест или обычный запуск — в логах при старте петля напишет mode=dynamic/static.
