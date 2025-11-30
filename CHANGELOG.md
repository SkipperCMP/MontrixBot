
# CHANGELOG

## 1.0.1+ REAL-ready (2025-11-12)
- UI: кнопка **Buy (Market)** вызывает `scripts/real_buy_market.py` через абсолютный путь и `sys.executable`.
- SAFE: `--ask` по умолчанию (ввод кода перед ордером).
- Логи: `[REAL][RUN] exe=..., script=...` для диагностики + JSON-ответ Binance в Log.
- Консоль: добавлены ланчер-скрипты `scripts/buy.ps1` и `scripts/buy.cmd`.
