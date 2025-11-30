
# MontrixBot 1.0.1-fix — REAL Sell + UI Close + TPSL scaffold

## Что входит
- `scripts/real_sell_market.py` — рыночная ПРОДАЖА (REAL) с SAFE-кодом (по умолчанию `--ask`).
- `scripts/sell.ps1`, `scripts/sell.cmd` — консольные ланчер-скрипты.
- `ui/app_step8.py` — **Close** должен вызывать `real_sell_market.py` аналогично Buy (Market). Если у вас уже моя версия UI (REAL-ready), просто замените файл из предыдущего патча; логика Close идентична buy.
- `runtime/tpsl_config.json` — черновой конфиг для TP/SL/Trailing (пока выключен).
- `core/tpsl_loop.py` — заготовка демона (пишет логи, без действий до 1.1).

## Применение
1) Распаковать в корень `MontrixBot_1.0.1` с заменой.
2) (REAL) Убедиться, что файл `SAFE_MODE` отсутствует и существует `runtime/safe_unlock.key`.
3) UI:
   - Запустить `python ui/app_step8.py`
   - Нажать **Close** — появится окно SAFE-code (как при покупке), в логе — JSON Binance.
4) Консоль:
   - PowerShell: `powershell -File scripts/sell.ps1 ADAUSDT 9`
   - CMD: `scripts\sell.cmd ADAUSDT 9`

## TPSL
- Сейчас **enabled=false**, `dry=true` — демон только пишет шаги в `runtime/health_log.jsonl`.
- В 1.1 включим расчёт и реальный SELL при срабатывании условий.
