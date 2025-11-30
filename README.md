
# MontrixBot 1.0_FINAL (UI‑polish 1.0.1‑pre)

## Quick Test Commands
```bash
# 1) Smoke test
python smoke_run.py

# 2) Health monitor (auto-restore exchange_info + JSONL snapshots)
python health_monitor.py

# 3) UI (SIM + SAFE by default)
python ui/app_step8.py
```

## Patch Mode (Windows)
```bat
run.cmd --patch
```
В режиме `--patch` выводится маркер и запускается стандартный сценарий (UI).

## Folders
- `runtime/` — рабочие файлы, снапшоты, логи:
  - `checkpoints/` — rolling snapshots каждые 5 минут (хранится 12 штук).
  - `health_log.jsonl` — снимки статуса каждые ~30s.
  - `trades.jsonl` — журнал сделок (для будущих релизов).

## Env
Положите `.env` в корень. Поддерживаются схемы ключей:
- `API_KEY`, `API_SECRET`
- `BINANCE_API_KEY`, `BINANCE_SECRET`

Проверка:
```bash
python tools/real_env_check.py
```

## Requirements (suggested)
Список в `requirements_suggested.txt`. Установка:
```bash
pip install -r requirements_suggested.txt
```
