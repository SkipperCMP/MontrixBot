MontrixBot 1.2-pre1 — STEP2 runtime bootstrap

Состав патча:
- core/signals.py
- ui/app_step8.py
- tools/runtime_bootstrap.py

Изменения:

1) core/signals.py
   - simple_rsi_macd теперь возвращает поле strength (0..1).
   - Добавлен dataclass SimpleSignal.strength.
   - simple_rsi_macd_signal заполняет strength для использования из UI.
   - Логика сигналов по RSI+MACD эквивалентна 1.1-SIGNALS, но дополнена оценкой силы.

2) tools/runtime_bootstrap.py
   - Новый helper ensure_ticks_bootstrap(symbol, max_points=300, interval="1m", min_points=50).
   - При необходимости подкачивает историю свечей с Binance REST (/api/v3/klines)
     и записывает в runtime/ticks_stream.jsonl "искусственные" тики (symbol/price/bid/ask/ts).
   - Все ошибки сети и I/O гасит, возвращая 0.

3) ui/app_step8.py
   - В начале файла добавлен импорт ensure_ticks_bootstrap с безопасным fallback.
   - В _load_chart_prices перед чтением файла вызывается ensure_ticks_bootstrap.
     При успешном bootstrap логируется строка вида:
       [BOOTSTRAP] seeded N ticks for ADAUSDT from Binance REST
   - В _refresh_indicators_and_signal:
       * в label Signal добавлен вывод strength: "Signal: BUY [0.63] (reason)"
       * в rec (runtime/signals.jsonl) добавлены поля:
           signal_strength
           recommendation_side
           recommendation_strength
           recommendation_trend
           recommendation_score

Применение:
- Распаковать поверх MontrixBot_1.2-pre1_BASELINE_clean с заменой core/signals.py,
  ui/app_step8.py и добавлением tools/runtime_bootstrap.py.
