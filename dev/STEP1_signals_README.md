MontrixBot 1.2-pre1 — STEP1: Signals polish
------------------------------------------------

Этот патч предназначен для базовой версии:
    MontrixBot_1.2-pre1_BASELINE_clean

Содержимое:
- core/signals.py
    * Добавлено поле strength в simple_rsi_macd/simple_rsi_macd_signal.
    * strength рассчитывается из глубины RSI и подтверждения MACD.
    * SimpleSignal.as_dict() теперь возвращает strength.
- ui/app_step8.py
    * Метка Signal: теперь показывает силу сигнала [0.00–1.00].
    * В runtime/signals.jsonl добавляются:
        - signal_strength
        - recommendation_side / recommendation_strength
        - recommendation_trend / recommendation_score
    * Лог [SIGNAL] и запись в signals.jsonl теперь только для side != HOLD.

Как применять:
1. Распаковать архив MontrixBot_1.2-pre1_BASELINE_clean.
2. Поверх него развернуть этот патч с заменой файлов:
    - core/signals.py
    - ui/app_step8.py
3. Запустить ui/app_step8.py как обычно.

Ожидаемый эффект:
- В верхней части окна рядом с Signal видно силу текущего сигнала.
- В Recommendation остаётся strength из core.advisor.
- Файл runtime/signals.jsonl обогащён полями для последующего анализа/графиков.
- Логи [SIGNAL] и файл signals.jsonl не засоряются HOLD-состояниями.
