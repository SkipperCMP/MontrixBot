from __future__ import annotations

from typing import Any, Mapping, Optional

import tkinter as tk
from tkinter import ttk

from tools.formatting import fmt_price, fmt_pnl


class MiniEquityBar:
    """
    Мини-панель портфеля для верхней части лейаута лога.

    Показывает:
      - Equity ($)
      - Day PnL %
      - Total PnL %
      - Open positions count

    Публичный интерфейс:
      - .frame                         — корневой фрейм
      - update(portfolio: dict | None) — обновить значения
    """

    def __init__(self, parent: tk.Misc) -> None:
        self._frame = ttk.Frame(parent, style="Dark.TFrame")

        # Основной контейнер слева-направо
        self._lbl_title = ttk.Label(
            self._frame,
            text="Portfolio:",
            style="Muted.TLabel",
        )
        self._lbl_title.pack(side=tk.LEFT, padx=(8, 6), pady=2)

        self._lbl_equity = ttk.Label(
            self._frame,
            text="Equity: $—",
            style="Dark.TLabel",
        )
        self._lbl_equity.pack(side=tk.LEFT, padx=(0, 10), pady=2)

        self._lbl_day = ttk.Label(
            self._frame,
            text="Day: —%",
            style="Dark.TLabel",
        )
        self._lbl_day.pack(side=tk.LEFT, padx=(0, 10), pady=2)

        self._lbl_total = ttk.Label(
            self._frame,
            text="Total: —%",
            style="Dark.TLabel",
        )
        self._lbl_total.pack(side=tk.LEFT, padx=(0, 10), pady=2)

        self._lbl_open = ttk.Label(
            self._frame,
            text="Open: 0",
            style="Dark.TLabel",
        )
        self._lbl_open.pack(side=tk.LEFT, padx=(0, 10), pady=2)

        # хранение последнего состояния при необходимости
        self._last_portfolio: Optional[dict[str, Any]] = None

    # ------------------------------------------------------------------ property

    @property
    def frame(self) -> ttk.Frame:
        return self._frame

    # ------------------------------------------------------------------ public API

    def update(self, portfolio: Mapping[str, Any] | None) -> None:
        """
        Ожидается формат (из UIAPI.snapshot_for_ui):

            {
                "equity": float | None,
                "pnl_day_pct": float | None,
                "pnl_total_pct": float | None,
                "open_positions_count": int | None,
            }
        """
        if portfolio is None:
            portfolio = {}

        self._last_portfolio = dict(portfolio)

        eq = portfolio.get("equity")
        day = portfolio.get("pnl_day_pct")
        total = portfolio.get("pnl_total_pct")
        open_cnt = portfolio.get("open_positions_count")

        # --- Equity ---
        try:
            if eq is None:
                txt_eq = "Equity: $—"
            else:
                txt_eq = f"Equity: ${fmt_price(eq)}"
            self._lbl_equity.configure(text=txt_eq)
        except tk.TclError:
            return

        # --- Day PnL% ---
        try:
            if day is None:
                txt_day = "Day: —%"
                fg_day = "#e6e6e6"
            else:
                v = float(day)
                txt_day = f"Day: {fmt_pnl(v)}%"
                if v > 0:
                    fg_day = "#a6f3a6"   # зелёный
                elif v < 0:
                    fg_day = "#ff6b6b"   # красный
                else:
                    fg_day = "#e6e6e6"
            self._lbl_day.configure(text=txt_day, foreground=fg_day)
        except Exception:
            # на всякий случай — без падения UI
            try:
                self._lbl_day.configure(text="Day: —%", foreground="#e6e6e6")
            except tk.TclError:
                pass

        # --- Total PnL% ---
        try:
            if total is None:
                txt_total = "Total: —%"
                fg_total = "#e6e6e6"
            else:
                v = float(total)
                txt_total = f"Total: {fmt_pnl(v)}%"
                if v > 0:
                    fg_total = "#a6f3a6"
                elif v < 0:
                    fg_total = "#ff6b6b"
                else:
                    fg_total = "#e6e6e6"
            self._lbl_total.configure(text=txt_total, foreground=fg_total)
        except Exception:
            try:
                self._lbl_total.configure(text="Total: —%", foreground="#e6e6e6")
            except tk.TclError:
                pass

        # --- Open positions ---
        try:
            cnt = int(open_cnt) if open_cnt is not None else 0
        except Exception:
            cnt = 0
        try:
            self._lbl_open.configure(text=f"Open: {cnt}")
        except tk.TclError:
            pass
