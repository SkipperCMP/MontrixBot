from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk


def build_log_ui(app: Any, StatusBar: Any) -> None:
    """Основная лог-панель + LastSig + StatusBar.

    Создаёт на `app`:
    - label_last_sig  — строка с последним сигналом
    - log             — tk.Text для основного лога
    - status_bar      — экземпляр StatusBar (если класс передан)
    """

    # Корневой фрейм лога
    frm = ttk.Frame(app, style="Log.TFrame")
    frm.pack(fill="both", expand=True, padx=8, pady=(4, 8))

    # ------------------------------------------------------------------ top row: Last signal + buttons
    top = ttk.Frame(frm, style="Log.TFrame")
    top.pack(fill="x", pady=(0, 4))

    app.label_last_sig = ttk.Label(
        top,
        text="Last signal: —",
        style="Muted.TLabel",
    )
    app.label_last_sig.pack(side="left", padx=(4, 4))

    # Кнопка очистки лога
    clear_cmd = getattr(app, "clear_log", None)
    if clear_cmd is None:
        clear_cmd = lambda: None

    btn_clear = ttk.Button(
        top,
        text="Clear log",
        style="Dark.TButton",
        command=clear_cmd,
    )
    btn_clear.pack(side="right", padx=(4, 6))

    # ------------------------------------------------------------------ middle: Text + scrollbar
    mid = ttk.Frame(frm, style="Log.TFrame")
    mid.pack(fill="both", expand=True)

    scrollbar = ttk.Scrollbar(mid, orient="vertical")
    scrollbar.pack(side="right", fill="y")

    log = tk.Text(
        mid,
        wrap="none",
        height=12,
        background="#121417",
        foreground="#e6e6e6",
        insertbackground="#e6e6e6",
        yscrollcommand=scrollbar.set,
    )
    scrollbar.configure(command=log.yview)

    try:
        log.configure(font=("Consolas", 9))
    except Exception:
        # Если шрифт недоступен – просто игнорируем
        pass

    log.pack(side="left", fill="both", expand=True, pady=(2, 0))

    app.log = log

    # ------------------------------------------------------------------ bottom: MiniEquity + Status bar
    # Мини-панель портфеля (может не создаться, тогда просто None)
    app.mini_equity = None
    try:
        from .mini_equity_bar import MiniEquityBar  # type: ignore
        try:
            me = MiniEquityBar(frm)
            # mini-equity располагаем над статус-баром, но у нижней кромки
            me.frame.pack(fill="x", side="bottom")
            app.mini_equity = me
        except Exception:
            app.mini_equity = None
    except Exception:
        app.mini_equity = None

    # Сам статус-бар — самый нижний элемент
    app.status_bar = None
    if StatusBar is not None:
        try:
            sb = StatusBar(frm)
            sb.frame.pack(fill="x", side="bottom")
            app.status_bar = sb
        except Exception:
            # Не даём упасть всему UI из-за статуса
            app.status_bar = None
