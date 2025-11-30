from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk


def build_log_ui(app: Any, StatusBar: Any) -> None:
    """Основная лог-панель + LastSig + StatusBar.

    Создаёт:
    - self.label_last_sig
    - self.log
    - self.status_bar
    """

    frm = ttk.Frame(app, style="Log.TFrame")
    frm.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    ttk.Label(
        frm,
        text="Log",
        style="Muted.TLabel",
        background="#121417",
    ).pack(anchor="w")

    # панель LastSig под заголовком лога
    try:
        app.label_last_sig = ttk.Label(
            frm,
            text="LastSig: n/a",
            style="Muted.TLabel",
            background="#121417",
        )
        app.label_last_sig.pack(anchor="w")
    except Exception:
        # в случае любых проблем с ttk просто продолжаем без панели
        app.label_last_sig = None

    app.log = tk.Text(
        frm,
        height=20,
        bg="#121417",
        fg="#cdd6f4",
        relief="flat",
    )
    try:
        app.log.configure(font=("Consolas", 9))
    except Exception:
        pass
    app.log.pack(fill="both", expand=True, pady=(2, 0))

    # Status bar (heartbeat / lag / last deal)
    app.status_bar = None
    if StatusBar is not None:
        try:
            app.status_bar = StatusBar(frm)
            app.status_bar.frame.pack(fill="x", side="bottom")
        except Exception:
            app.status_bar = None
