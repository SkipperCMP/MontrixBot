MontrixBot 1.2-pre1 — STEP1.5 Signals+UI patch

Состав:
- ui/app_step8.py
- core/signals.py
- tools/runtime_bootstrap.py
- dev/STEP1.5_signals_plus_UI_README.md

Изменения Step1.5:
1) ui/app_step8.py
   - В _refresh_indicators_and_signal() блок advisor recommendation перенесён
     сразу после обновления label_signal (Signal: ...).
   - Текст рекомендации остаётся в отдельном label_reco:
       Recommendation: BUY ↑ (0.53)  trend=UP, MACD bullish, ...
   - Блок записи в runtime/signals.jsonl теперь дополняет запись полями
     рекомендации советника (если reco — dict):
       recommendation_side
       recommendation_strength
       recommendation_trend
       recommendation_score
       recommendation_reason
   - Эти поля записываются только при смене сигнала (как и раньше).

2) core/signals.py
   - Без изменений относительно STEP1_signals_strength_patch:
     simple_rsi_macd / SimpleSignal / simple_rsi_macd_signal уже возвращают
     поле strength (0..1), которое используется в UI и в JSON
     (signal_strength).

3) tools/runtime_bootstrap.py
   - Перенесён из предыдущего патча для совместимости (логика не менялась).

Применение:
- Распаковать архив поверх текущего состояния MontrixBot_1.2-pre1
  (где уже установлены STEP2 + NoneFix + STEP1_signals_strength_patch)
  с заменой файлов:
    ui/app_step8.py
    core/signals.py
    tools/runtime_bootstrap.py

Результат:
- Верхняя панель показывает:
    Signal: BUY [0.63] (RSI oversold, MACD confirms up)
    Recommendation: BUY ↑ (0.51)  trend=UP, ...
- Файл runtime/signals.jsonl для каждой смены сигнала содержит как strength
  простого сигнала, так и поля рекомендации советника.
