from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk


def build_activepos_ui(app: Any, parent: Any = None) -> None:
    """Панель 'Active position (SIM)'.

    Создаёт:
    - self.btn_reset_sim
    - self.active_box
    и заполняет текстом '— no active positions —'.

    parent (optional):
    - UI container where the panel should be mounted (e.g. a tab frame).
    - app remains the state/behavior owner; widget attributes are set on app.
    """

    host = parent if parent is not None else app

    frm = ttk.Frame(host, style="Dark.TFrame")
    frm.pack(fill="x", padx=8, pady=(0, 6))

    header = ttk.Frame(frm, style="Dark.TFrame")
    header.pack(fill="x")

    ttk.Label(
        header,
        text="Active positions (SIM)",
        style="Muted.TLabel",
    ).pack(side="left", anchor="w")

    # v2.2.90 (UI Read-Only Hardening): no action surface.
    # Reset SIM used to call UIAPI.reset_sim_state() (runtime side-effect).
    # Keep attribute for backward-compat, but do not expose a button.
    app.btn_reset_sim = None

    app.active_box = tk.Text(
        frm,
        height=6,
        bg="#121417",
        fg="#cdd6f4",
        relief="flat",
    )
    try:
        app.active_box.configure(font=("Consolas", 9))
    except Exception:
        pass

    # цветовые теги для PnL-колонки и направления позиции
    try:
        app.active_box.tag_configure("pnl_pos", foreground="#a6e3a1")    # зелёный
        app.active_box.tag_configure("pnl_neg", foreground="#f38ba8")    # красный
        app.active_box.tag_configure("side_long", foreground="#a6e3a1")  # LONG
        app.active_box.tag_configure("side_short", foreground="#f38ba8") # SHORT
    except Exception:
        pass

    # маркеры тренда в последней колонке (пули)
    try:
        app.active_box.tag_configure("trend_up", foreground="#7ddc84")     # зелёный dot
        app.active_box.tag_configure("trend_down", foreground="#ff7a7a")   # красный dot
        app.active_box.tag_configure("trend_flat", foreground="#9aa3ad")   # серый dot
    except Exception:
        pass

    app.active_box.pack(fill="x", pady=(2, 0))
    app._set_active_text("— no active positions —")

