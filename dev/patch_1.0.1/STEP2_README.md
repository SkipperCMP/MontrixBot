
# 1.0.1 Step2 — Retry/Throttle + SAFE Lock 2FA + Error Decode
Дата: 2025-11-12T09:16:10.306333Z

Добавлено:
- `tools/api_throttle.py` — rate-limit + backoff
- `tools/binance_errors.py` — перевод кодов ошибок в понятные сообщения
- `tools/safe_lock.py` — файл-ключ `runtime/safe_unlock.key` для временного обхода SAFE
- `core/orders_real.py` — обёртка над python-binance `create_order` с guard'ами

Как использовать:
1) Установите зависимости из `requirements_suggested.txt` (добавьте `python-binance` при необходимости).
2) Создайте ключ для разблокировки SAFE:
   ```py
   from tools.safe_lock import set_unlock_key
   set_unlock_key("123456")
   ```
3) Вызов реального ордера:
   ```py
   from core.orders_real import place_order_real
   resp = place_order_real("ADAUSDT", "BUY", type_="MARKET", quantity=10.0, safe_code="123456")
   ```
Без корректного `safe_code` при наличии файла `SAFE_MODE` отправка будет заблокирована.
