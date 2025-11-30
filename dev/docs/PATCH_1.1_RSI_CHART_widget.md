# MontrixBot 1.1 — PATCH: RSI Chart Widget (ChartPanel)

Этот патч добавляет реальную реализацию виджета графика:

  ui/widgets/chart_panel.py

Вместо заглушки (`print('chart_panel placeholder created')`) теперь:
  - создаётся Matplotlib‑фигура с двумя областями:
      • верхняя — ценовой график (линия по цене);
      • нижняя — RSI (0–100) с уровнями 30/70.
  - используется core.indicators.rsi (если модуль доступен);
  - при отсутствии Matplotlib панель не ломает приложение, а
    показывает простую надпись.

ВАЖНО:
  - Патч НЕ подключён автоматически к текущему app_step8.py
    (минималистичному UI 1.0.1).
  - Это строительный блок для полноценного UI 1.1: ChartPanel можно
    будет встроить в новый/расширенный интерфейс без изменения ядра.

Публичный API:
  - class ChartPanel(ttk.Frame):
      • plot_series(times, prices, rsi_values=None, rsi_period=14)
      • clear()

Интеграция в будущем (пример):
  from ui.widgets.chart_panel import ChartPanel

  panel = ChartPanel(parent_frame)
  panel.pack(fill="both", expand=True)

  # при обновлении данных:
  panel.plot_series(times, close_prices)

Патч безопасен для baseline 1.0.1: текущий UI и логика не изменяются.
