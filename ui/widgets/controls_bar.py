from __future__ import annotations

from pathlib import Path
from typing import Sequence, Any

import tkinter as tk
from tkinter import ttk


def build_topbar_ui(app: Any, symbols: Sequence[str]) -> None:
    """Строит верхнюю панель управления.

    Лево: Symbol / Qty / BUY / Close / Panic / Mode / SAFE / Dry-Run.
    Право: индикаторы Signal / Recommendation / MACD / RSI.
    """

    top = ttk.Frame(app, style="Dark.TFrame")
    top.pack(fill="x", padx=8, pady=6)

    # --- левый блок: Symbol + Qty + кнопки ---
    left_box = ttk.Frame(top, style="Dark.TFrame")
    left_box.pack(side="left", padx=(4, 4))

    lbl_sym = ttk.Label(left_box, text="Symbol:", style="Dark.TLabel")
    lbl_sym.pack(side="left", padx=(0, 4))

    values = list(symbols) if symbols else []
    if not hasattr(app, "var_symbol"):
        app.var_symbol = tk.StringVar(value=values[0] if values else "")
    app.cmb_symbol = ttk.Combobox(
        left_box,
        textvariable=app.var_symbol,
        values=values,
        width=12,
        state="readonly",
        style="ComboDark.TCombobox",
    )
    app.cmb_symbol.pack(side="left", padx=(0, 8))

    lbl_qty = ttk.Label(left_box, text="Qty:", style="Dark.TLabel")
    lbl_qty.pack(side="left", padx=(0, 4))

    if not hasattr(app, "var_qty"):
        app.var_qty = tk.StringVar(value="0.0")
    app.entry_qty = ttk.Entry(
        left_box,
        textvariable=app.var_qty,
        width=10,
        style="EntryDark.TEntry",
    )
    app.entry_qty.pack(side="left", padx=(0, 8))

    # --- кнопки BUY / Close / Panic ---
    buy_cmd = getattr(app, "on_buy_sim", None) or (lambda: None)
    close_cmd = getattr(app, "on_close_sim", None) or (lambda: None)
    panic_cmd = getattr(app, "on_panic", None) or (lambda: None)

    app.btn_buy = ttk.Button(
        left_box,
        text="BUY",
        style="Dark.TButton",
        command=buy_cmd,
    )
    app.btn_buy.pack(side="left", padx=2)

    app.btn_close = ttk.Button(
        left_box,
        text="Close",
        style="Dark.TButton",
        command=close_cmd,
    )
    app.btn_close.pack(side="left", padx=2)

    app.btn_panic = ttk.Button(
        left_box,
        text="Panic",
        style="Dark.TButton",
        command=panic_cmd,
    )
    app.btn_panic.pack(side="left", padx=2)

    # --- переключатель SIM/REAL ---
    if not hasattr(app, "_mode"):
        app._mode = "SIM"

    if not hasattr(app, "var_mode"):
        app.var_mode = tk.StringVar(value=f"Mode: {app._mode}")

    toggle_mode_cmd = getattr(app, "_toggle_mode", None) or (lambda: None)
    app.btn_mode = ttk.Button(
        left_box,
        textvariable=app.var_mode,
        style="Dark.TButton",
        command=toggle_mode_cmd,
    )
    app.btn_mode.pack(side="left", padx=(8, 4))

    # --- бейдж SAFE ---
    badge_safe = ttk.Label(
        left_box,
        text="SAFE",
        style="BadgeSafe.TLabel",
        cursor="hand2",
    )
    badge_safe.pack(side="left", padx=(4, 4))
    if hasattr(app, "_toggle_safe"):
        badge_safe.bind("<Button-1>", lambda e: app._toggle_safe())
    app.badge_safe = badge_safe

    # --- бейдж Dry-Run / REAL CLI ---
    badge_dry = ttk.Label(
        left_box,
        text="Dry-Run",
        style="BadgeWarn.TLabel",
        cursor="hand2",
    )
    badge_dry.pack(side="left", padx=(0, 4))
    if hasattr(app, "_toggle_dry"):
        badge_dry.bind("<Button-1>", lambda e: app._toggle_dry())
    app.badge_dry = badge_dry

    # --- правый блок: сигналы / индикаторы ---
    right_box = ttk.Frame(top, style="Dark.TFrame")
    right_box.pack(side="right", padx=(4, 4))

    app.label_reco = ttk.Label(
        right_box,
        text="Recommendation: n/a",
        style="Muted.TLabel",
    )
    app.label_reco.pack(side="right", padx=(4, 0))

    app.label_signal = ttk.Label(
        right_box,
        text="Signal: n/a",
        style="Muted.TLabel",
    )
    app.label_signal.pack(side="right", padx=(4, 0))

    app.label_macd = ttk.Label(
        right_box,
        text="MACD: n/a",
        style="Muted.TLabel",
    )
    app.label_macd.pack(side="right", padx=(4, 0))

    app.label_rsi = ttk.Label(
        right_box,
        text="RSI: n/a",
        style="Muted.TLabel",
    )
    app.label_rsi.pack(side="right", padx=(4, 0))


def build_paths_ui(app: Any, journal_file: Path, runtime_dir: Path) -> None:
    """Строит вторую строку с кнопками открытия журналов / runtime / графиков."""

    box = ttk.Frame(app, style="Dark.TFrame")
    box.pack(fill="x", padx=8, pady=(0, 8))

    ttk.Button(
        box,
        text="Open Journal (trades.jsonl)",
        style="Dark.TButton",
        command=lambda: app._open_path(journal_file),
    ).pack(side="left", padx=4)

    ttk.Button(
        box,
        text="Open Journal (viewer)",
        style="Dark.TButton",
        command=app._cmd_open_trades,
    ).pack(side="left", padx=4)

    ttk.Button(
        box,
        text="Open runtime folder",
        style="Dark.TButton",
        command=lambda: app._open_path(runtime_dir),
    ).pack(side="left", padx=4)

    ttk.Button(
        box,
        text="Open Signals",
        style="Dark.TButton",
        command=app._cmd_open_signals,
    ).pack(side="left", padx=4)

    ttk.Button(
        box,
        text="Open RSI Chart (demo)",
        style="Dark.TButton",
        command=app._open_rsi_chart,
    ).pack(side="left", padx=4)

    ttk.Button(
        box,
        text="Open LIVE Chart",
        style="Dark.TButton",
        command=app._open_rsi_live_chart,
    ).pack(side="left", padx=4)
