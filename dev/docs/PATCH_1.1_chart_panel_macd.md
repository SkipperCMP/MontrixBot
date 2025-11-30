# Patch 1.1 — ChartPanel with MACD

Этот патч обновляет `ui/widgets/chart_panel.py`, добавляя:

- трёхпанельный график: Price (верх), RSI (середина), MACD (низ);
- расчёт MACD (EMA12-EMA26) и сигнальной линии (EMA9 от MACD);
- гистограмму MACD;
- аккуратные отступы вместо `tight_layout`, без предупреждений Matplotlib.

Публичный API `ChartPanel.plot_series(times, prices, ...)` сохранён,
существующий код в `ui/app_step8.py` продолжит работать без изменений.
