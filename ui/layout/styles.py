# ui/layout/styles.py
from __future__ import annotations

from typing import Any, Callable, Optional

from tkinter import ttk


def apply_styles(app: Any, apply_neutral_dark: Optional[Callable[[ttk.Style], dict]]) -> None:
    """
    Вынесенная версия App._build_styles.

    Ничего не меняет по поведению: всё тот же набор стилей и fallback
    на старую dark-схему, только теперь живёт в отдельном модуле.
    """
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    # Пытаемся применить общую dark-тему
    palette_bg = None
    if apply_neutral_dark is not None:
        try:
            palette = apply_neutral_dark(style)
            if isinstance(palette, dict):
                palette_bg = palette.get("bg")
        except Exception:
            palette_bg = None

    # Fallback на старую схему, если тема не применилась
    if palette_bg is None:
        # старые значения из app_step9 (ранее app_step8)
        bg = "#1c1f24"
        fg = "#e6e6e6"
        muted = "#9aa0a6"

        style.configure("Dark.TFrame", background=bg)
        style.configure("Dark.TLabel", background=bg, foreground=fg)
        style.configure("Muted.TLabel", background=bg, foreground=muted)
        style.configure(
            "BadgeSafe.TLabel",
            background="#26a269",
            foreground="#0b0b0b",
            borderwidth=1,
            relief="solid",
            padding=(8, 2),
            highlightthickness=1,
            highlightbackground="#ffffff",
        )
        style.configure(
            "BadgeWarn.TLabel",
            background="#d0b343",
            foreground="#0b0b0b",
            borderwidth=1,
            relief="solid",
            padding=(8, 2),
            highlightthickness=1,
            highlightbackground="#ffffff",
        )
        style.configure(
            "BadgeDanger.TLabel",
            background="#e01b24",
            foreground="#0b0b0b",
            padding=(8, 2),
        )
    else:
        # если тема отдала палитру — подстраиваем фон окна под неё
        try:
            app.configure(bg=palette_bg)
        except Exception:
            pass

    # Общие стили кнопок / полей
    style.configure("Dark.TButton", padding=6)
    style.map("Dark.TButton", background=[("active", "#2a2f36")])

    # --- AUTOSIM toggle styles (green=ON, red=OFF ---
    style.configure("AutosimOff.TButton", padding=6)
    style.map(
        "AutosimOff.TButton",      
        background=[("!disabled", "#e01b24"), ("active", "#b3161d")],
        foreground=[("!disabled", "#0b0b0b")],
    )

    style.configure("AutosimOn.TButton", padding=6)
    style.map(
        "AutosimOn.TButton",
        background=[("!disabled", "#26a269"), ("active", "#1f8a5c")],
        foreground=[("!disabled", "#0b0b0b")],
    )

    style.configure("Log.TFrame", background="#121417")
    style.configure(
        "EntryDark.TEntry",
        fieldbackground="#121417",
        foreground="#e6e6e6",
    )
    style.configure(
        "ComboDark.TCombobox",
        fieldbackground="#121417",
        foreground="#e6e6e6",
    )
