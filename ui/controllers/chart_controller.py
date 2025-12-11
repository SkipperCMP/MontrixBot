# ui/controllers/chart_controller.py
from __future__ import annotations

from typing import Any, Callable, Optional

import tkinter as tk
from tkinter import messagebox


class ChartController:
    """Управление RSI / LIVE-окнами с графиками.

    Вынесено из ui.app_step9.App:
    - _open_rsi_chart
    - _open_rsi_live_chart

    Логика загрузки цен остаётся в App._load_chart_prices.
    """

    def __init__(self, app: Any, chart_panel_cls: Optional[Callable[..., Any]]) -> None:
        self.app = app
        self.ChartPanel = chart_panel_cls
        self._last_snapshot: dict | None = None  # STEP1.3.1: hook для TickUpdater

    # ------------------------------------------------------------------ helpers

    def _ensure_chartpanel(self, title: str) -> Optional[tuple[tk.Toplevel, Any]]:
        """Создаёт окно и ChartPanel, если доступен matplotlib."""
        ChartPanel = self.ChartPanel
        if ChartPanel is None:
            messagebox.showwarning(title, "ChartPanel / matplotlib недоступны.")
            return None

        win = tk.Toplevel(self.app)
        win.title(title)
        win.geometry("800x500")

        panel = ChartPanel(win)
        panel.pack(fill="both", expand=True)

        return win, panel   

    # ------------------------------------------------------------------ API
    
    def update_from_snapshot(self, snapshot: dict | None) -> None:
        """Получает снапшот ядра от TickUpdater.

        Текущая версия:
        - просто запоминает снапшот и версию;
        - не трогает существующую логику обновления графика.

        Позже сюда можно будет добавить:
        - обновление буфера тиков;
        - триггер мягкого перерисовывания LIVE-чарта.
        """
        if snapshot is None:
            return

        try:
            # сохраняем последний снапшот для возможного дальнейшего использования
            self._last_snapshot = dict(snapshot)
        except Exception:
            # защита от странных типов / прокси
            self._last_snapshot = snapshot

    def open_rsi_chart(self) -> None:
        """Открыть статический RSI-график (demo)."""
        res = self._ensure_chartpanel("MontrixBot — RSI Chart (demo 1.1)")
        if res is None:
            return
        win, panel = res

        try:
            times, prices = self.app._load_chart_prices(max_points=300)
            if times and prices:
                panel.plot_series(times, prices)
        except Exception as e:  # noqa: BLE001
            try:
                messagebox.showwarning("RSI Chart", f"Ошибка построения графика: {e!r}")
            except Exception:
                pass

    def open_rsi_live_chart(self) -> None:
        """Открыть LIVE-график с периодическим обновлением."""
        res = self._ensure_chartpanel("MontrixBot — LIVE Chart (ticks=300)")
        if res is None:
            return
        win, panel = res

        def refresh() -> None:
            if not win.winfo_exists():
                return
            try:
                times, prices = self.app._load_chart_prices(max_points=300)
                if times and prices:
                    panel.plot_series(times, prices)
            except Exception:
                # поведение такое же, как и было: молча пропускаем ошибку отрисовки
                pass
            else:
                # планируем следующий апдейт, пока окно живо
                try:
                    win.after(1000, refresh)
                except Exception:
                    return

        try:
            refresh()
        except Exception:
            # если первый вызов не удался, просто не запускаем цикл
            return
