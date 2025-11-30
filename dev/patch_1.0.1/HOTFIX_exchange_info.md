
# Hotfix — exchange_info.json repair
Проблема: в runtime/exchange_info.json встретилась неканоничная структура (список строк).
Решение:
- Обновлен core/binance_filters.py (устойчивый парсер, авто-fetch нужного символа).
- Добавлен tools/fetch_exchange_info.py (ручной/авто-запрос exchangeInfo).
- Обновлен scripts/real_sandbox_buy.py (сам чинит файл при ошибке).

Быстрый фикс вручную:
    python tools/fetch_exchange_info.py ADAUSDT
