
from __future__ import annotations
from typing import List, Dict, Any, Callable, Optional
import tkinter as tk
from tkinter import ttk

# Таблица позиций: полностью binder-driven, без локальных «истин».
# Источник данных: rows = select_open_positions(binder.get_ui_state())
# Форматирование передаётся извне — через функции-форматтеры.

class PositionsTable:
    def __init__(
        self,
        tree: ttk.Treeview,
        *,
        fmt_qty: Callable[[float], str],
        fmt_price: Callable[[float], str],
        fmt_pnl: Callable[[float], str],
    ) -> None:
        self.tree = tree
        self.fmt_qty = fmt_qty
        self.fmt_price = fmt_price
        self.fmt_pnl = fmt_pnl

        self._sort_key: str = "symbol"
        self._sort_desc: bool = False
        self._degraded: bool = False
        self._empty_label: Optional[tk.Label] = None

        # Заголовки с кликабельной сортировкой
        for col in ("symbol", "qty", "avg_price", "last", "unrealized_pnl", "status"):
            self.tree.heading(col, text=self._title(col),
                              command=lambda c=col: self.set_sort(c))

    # ----- Публичные методы -----
    def set_sort(self, column: str, *, desc: Optional[bool] = None) -> None:
        if desc is None:
            if column == self._sort_key:
                self._sort_desc = not self._sort_desc
            else:
                self._sort_key, self._sort_desc = column, False
        else:
            self._sort_key, self._sort_desc = column, bool(desc)

    def set_degraded(self, value: bool) -> None:
        self._degraded = bool(value)

    def update(self, rows: List[Dict[str, Any]]) -> None:
        # EMPTY / DEGRADED состояния — мягкие, не ломают таблицу
        if self._degraded:
            self._show_overlay("reconnecting…")
        elif not rows:
            self._show_overlay("no positions")
        else:
            self._hide_overlay()

        # Стабильная сортировка
        key = self._sort_key
        desc = self._sort_desc

        def key_fn(r: Dict[str, Any]):
            v = r.get(key)
            if isinstance(v, (int, float)):
                return v
            return str(v or "")
        rows_sorted = sorted(rows, key=key_fn, reverse=desc)

        # Полная перерисовка (простая и надёжная)
        self.tree.delete(*self.tree.get_children())
        for r in rows_sorted:
            self.tree.insert(
                "", tk.END,
                values=(
                    r.get("symbol", "—"),
                    self.fmt_qty(r.get("qty", 0.0)),
                    self.fmt_price(r.get("avg_price", 0.0)),
                    self.fmt_price(r.get("last", 0.0)),
                    self.fmt_pnl(r.get("unrealized_pnl", 0.0)),
                    r.get("status", ""),
                ),
            )

    # ----- Вспомогательные -----
    def _title(self, col: str) -> str:
        mapping = {
            "symbol": "Symbol",
            "qty": "Qty",
            "avg_price": "Avg Price",
            "last": "Last",
            "unrealized_pnl": "uPnL",
            "status": "Status",
        }
        return mapping.get(col, col)

    def _show_overlay(self, text: str) -> None:
        if self._empty_label is None:
            parent = self.tree.master
            self._empty_label = tk.Label(parent, text=text, anchor="center")
            self._empty_label.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self._empty_label.configure(text=text)
            self._empty_label.lift()

    def _hide_overlay(self) -> None:
        if self._empty_label is not None:
            self._empty_label.lower()
