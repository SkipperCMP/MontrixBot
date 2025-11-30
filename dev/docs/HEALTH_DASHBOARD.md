
# Health Dashboard for MontrixBot 1.0.1-fix

## Быстрый запуск (без интеграции в UI)
1) Скопируйте файлы из архива в корень `MontrixBot_1.0_FINAL` с сохранением путей.
2) Запустите параллельно с ботом:
   - `run_health.cmd` — сбор heartbeat в `runtime/health.log` (у вас уже есть).
   - `run_dashboard.cmd` — окно Health Dashboard (чтение `health.log`, автообновление каждые 5 сек).

## Интеграция в основной UI (для 1.0.1-fix)
- Виджет `ui/health_widget.py` можно подключить из `ui/app_step8.py`, добавив кнопку **Open Health**,
  которая открывает `tk.Toplevel()` с `HealthPanel(..., refresh_sec=5)`.
- Такой подход не ломает Single Focus логику и не влияет на freeze 1.0.

## Формат health.log
Строка:
`YYYY-MM-DD HH:MM:SS UTC | mode=REAL dry_run=True safe=ON | trades=553B open=2 close=2 active=[] last_ts=...`

## Настройка частоты
- Частоту записи строк задаёт `run_health.cmd` → `--interval 60` (в секундах).
- В дашборде `refresh_sec=5` (можете повысить/понизить в `scripts/health_dashboard.py`).

