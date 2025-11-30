MontrixBot 1.0.1 — Step 2: UI integration (TPSL badge)
Date: 2025-11-12 20:16:19 UTC

Файлы в патче:
- ui/tpsl_status_badge.py — виджет бейджа TPSL в тёмной теме (зелёный/красный).
- MontrixBot_1.0.1_READY/ui/app.py — в этот файл внедрён код, который читает runtime/settings.json и показывает статус TPSL в верхней панели (справа).

Как применить:
1) Распаковать в корень проекта с заменой.
2) Запустить GUI как обычно — бейдж появится справа в верхней панели (рядом с SAFE/Dry-Run, если удачно определён контейнер).

Если контейнер верхней панели назван иначе:
- Открой MontrixBot_1.0.1_READY/ui/app.py и в блоке 'TPSL badge injection' поменяй переменную _badge_parent на нужный контейнер (например, topbar_frame).
