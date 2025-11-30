MontrixBot 1.2-pre1 — STEP1+STEP2 signals strength patch

Файлы:
- ui/app_step8.py
- core/signals.py
- tools/runtime_bootstrap.py

Основные изменения:

1) core/signals.py
   - Полностью реализован simple_rsi_macd с оценкой strength (0..1).
   - Добавлен dataclass SimpleSignal со свойством strength и методом as_dict().
   - simple_rsi_macd_signal использует simple_rsi_macd и возвращает SimpleSignal со strength.

2) ui/app_step8.py
   - Импортирован ensure_ticks_bootstrap из tools.runtime_bootstrap с безопасным fallback.
   - _load_chart_prices: перед чтением ticks_stream.jsonl вызывается ensure_ticks_bootstrap(...)
     и при успешном bootstrap в лог пишется:
       [BOOTSTRAP] seeded N ticks for ADAUSDT from Binance REST
   - _compute_last_indicators:
       * добавлена проверка на None/NaN и всегда возвращаются float или None-тройка.
   - _refresh_indicators_and_signal:
       * ранний выход, если SIGNALS отсутствует или индикаторы ещё не готовы;
       * при формировании label_signal выводится сила сигнала:
           Signal: BUY [0.63] (RSI oversold, MACD confirms up)
       * в signals.jsonl добавлено поле signal_strength.

3) tools/runtime_bootstrap.py
   - Включён актуальный вариант ensure_ticks_bootstrap (или безопасный stub, если исходник недоступен).

Установка:
- Распаковать архив поверх MontrixBot_1.2-pre1_BASELINE_clean (текущего 1.2-pre1) с заменой:
    ui/app_step8.py
    core/signals.py
    tools/runtime_bootstrap.py

После установки:
- В верхней панели рядом с сигналом появится сила в диапазоне [0.00..1.00].
- В runtime/signals.jsonl в каждой записи будет поле "signal_strength".
