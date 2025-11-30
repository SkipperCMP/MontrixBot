from __future__ import annotations

from pathlib import Path
from typing import Sequence, Any

import tkinter as tk
from tkinter import ttk


def build_topbar_ui(app: Any, symbols: Sequence[str]) -> None:
    """Строит верхнюю панель управления (symbol/qty/кнопки/бейджи/мини-equity/индикаторы)."""

    top = ttk.Frame(app, style="Dark.TFrame")
    top.pack(fill="x", padx=8, pady=6)

    # --- левый блок: Symbol + Qty + Preview/Clear ---
    ttk.Label(top, text="Symbol:", style="Dark.TLabel").pack(
        side="left", padx=(4, 4)
    )

    app.combo = ttk.Combobox(
        top,
        values=list(symbols),
        textvariable=app.var_symbol,
        width=12,
        state="readonly",
    )
    app.combo.pack(side="left", padx=(0, 12))

    ttk.Label(top, text="Qty:", style="Dark.TLabel").pack(side="left")

    app.entry_qty = ttk.Entry(
        top,
        textvariable=app.var_qty,
        width=8,
        style="EntryDark.TEntry",
    )
    app.entry_qty.pack(side="left", padx=(4, 12))

    app.btn_preview = ttk.Button(
        top,
        text="Preview",
        style="Dark.TButton",
        command=app.on_preview,
    )
    app.btn_preview.pack(side="left", padx=2)

    app.btn_clear = ttk.Button(
        top,
        text="Clear log",
        style="Dark.TButton",
        command=app.clear_log,
    )
    app.btn_clear.pack(side="left", padx=2)

    # --- блок Buy / Close / Panic ---
    # команды для Buy/Close навешиваются позже в _set_mode()
    app.btn_buy = ttk.Button(
        top,
        text="Buy (Market)",
        style="Dark.TButton",
    )
    app.btn_buy.pack(side="left", padx=6)

    app.btn_close = ttk.Button(
        top,
        text="Close",
        style="Dark.TButton",
    )
    app.btn_close.pack(side="left", padx=2)

    app.btn_panic = ttk.Button(
        top,
        text="Panic",
        style="Dark.TButton",
        command=app.on_panic,
    )
    app.btn_panic.pack(side="left", padx=2)

    # --- переключатель SIM/REAL ---
    if not hasattr(app, "var_mode") or not isinstance(
        getattr(app, "var_mode"), tk.StringVar
    ):
        app.var_mode = tk.StringVar(value="Mode: SIM")

    app.btn_mode = ttk.Button(
        top,
        textvariable=app.var_mode,
        style="Dark.TButton",
        command=app._toggle_mode,
    )
    app.btn_mode.pack(side="left", padx=(18, 4))

    # --- бейджи Dry-Run / SAFE ---
    app.badge_dry = ttk.Label(top, text="Dry-Run", style="BadgeWarn.TLabel")
    app.badge_dry.pack(side="left", padx=(0, 6))

    app.badge_safe = ttk.Label(top, text="SAFE", style="BadgeSafe.TLabel")
    app.badge_safe.pack(side="left", padx=(0, 0))

    # хинты/подсказки по бейджам
    app.badge_dry.bind(
        "<Enter>",
        lambda e: app._set_status("Dry-Run = CLI-скрипты с подтверждением (--ask)"),
    )
    app.badge_dry.bind(
        "<Leave>",
        lambda e: app._set_status(""),
    )
    app.badge_dry.bind(
        "<Button-1>",
        lambda e: app._toggle_dry(),
    )

    app.badge_safe.bind(
        "<Enter>",
        lambda e: app._set_status("SAFE = блокировка реальных ордеров"),
    )
    app.badge_safe.bind(
        "<Leave>",
        lambda e: app._set_status(""),
    )
    app.badge_safe.bind(
        "<Button-1>",
        lambda e: app._toggle_safe(),
    )

    # --- mini equity bar ---
    if not hasattr(app, "var_equity") or not isinstance(
        getattr(app, "var_equity"), tk.StringVar
    ):
        app.var_equity = tk.StringVar(value="Equity: —")

    lbl_equity = ttk.Label(
        top,
        textvariable=app.var_equity,
        style="Dark.TLabel",
    )
    lbl_equity.pack(side="left", padx=(4, 8))

    # --- правый блок: индикаторы рекомендации/сигнала/RSI/MACD ---
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
