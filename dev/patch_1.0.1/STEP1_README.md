
## 1.0.1 Step1 — Time Sync + Hard Filters

- `tools/binance_time_sync.py`:
  - `sync_time()` — сохраняет `runtime/time_offset.json`
  - `signed_params_with_ts(params)` — добавляет скорректированный `timestamp` и `recvWindow`
- `core/binance_filters.py`:
  - жёсткое округление цены/объёма по `PRICE_FILTER` и `LOT_SIZE`
  - проверка `MIN_NOTIONAL/NOTIONAL`

**Важно:** Для полной интеграции в REAL-ордеры добавим вызовы в `OrderExecutor` на шаге 2 (Retry/Throttle/REAL). Пока фильтры влияют на Preview и доступны как утилиты.
