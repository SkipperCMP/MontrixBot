from __future__ import annotations

from pathlib import Path
from typing import Sequence, Any

import os
import tkinter as tk
from tkinter import ttk


def build_topbar_ui(app: Any, symbols: Sequence[str]) -> None:
    """Строит верхнюю панель управления.

    Лево: Read-Only banner / Symbol / SAFE / Dry-Run.
    Право: индикаторы Signal / Recommendation / MACD / RSI.

    MontrixBot v2.2.90 — UI Read-Only Hardening (No Action Surface):
    - Убраны все кнопки/переключатели, которые выглядят как управление торговлей
      (BUY, Close, Panic, Mode SIM/REAL).
    - SAFE и Dry-Run остаются только как индикаторы (без кликов).
    """

    top = ttk.Frame(app, style="Dark.TFrame")
    top.pack(fill="x", padx=8, pady=6)

    # --- левый блок: Read-Only banner + Symbol + индикаторы ---
    left_box = ttk.Frame(top, style="Dark.TFrame")
    left_box.pack(side="left", padx=(4, 4))

    # READ-ONLY banner
    ttk.Label(
        left_box,
        text="UI: READ-ONLY",
        style="Muted.TLabel",
    ).pack(side="left", padx=(0, 12))

    # AUTOSIM toggle (SIM-only). This does not control REAL and does not place orders.
    # It only starts/stops the local AUTOSIM loop for SIM diagnostics.
    toggle_cmd = getattr(app, "_cmd_autosim_toggle", None) or (lambda: None)
    app.btn_autosim_toggle = ttk.Button(
        left_box,
        text="START",
        style="AutosimOff.TButton",
        command=toggle_cmd,
    )
    app.btn_autosim_toggle.pack(side="left", padx=(0, 12))

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

    # NOTE: Qty / BUY / Close / Panic / Mode removed in v2.2.90 (read-only hardening)

    # --- бейдж SAFE (fixed size, white border via wrapper) ---
    badge_safe_wrap = tk.Frame(
        left_box,
        bg="#ffffff",
        highlightthickness=0,
        bd=0,
        width=54,
        height=24,
    )
    badge_safe_wrap.pack_propagate(False)
    badge_safe_wrap.pack(side="left", padx=(6, 6), pady=(0, 0))

    badge_safe = ttk.Label(
        badge_safe_wrap,
        text="SAFE",
        style="BadgeSafe.TLabel",
        width=7,
        anchor="center",
    )
    badge_safe.pack(padx=1, pady=1, fill="both", expand=True)
    # read-only: no click bindings

    app.badge_safe = badge_safe

    # --- бейдж Dry-Run / REAL CLI (fixed size, white border via wrapper) ---
    badge_dry_wrap = tk.Frame(
        left_box,
        bg="#ffffff",
        highlightthickness=0,
        bd=0,
        width=72,
        height=24,
    )
    badge_dry_wrap.pack_propagate(False)
    badge_dry_wrap.pack(side="left", padx=(0, 6), pady=(0, 0))

    badge_dry = ttk.Label(
        badge_dry_wrap,
        text="Dry-Run",
        style="BadgeWarn.TLabel",
        width=9,
        anchor="center",
    )
    badge_dry.pack(padx=1, pady=1, fill="both", expand=True)
    # read-only: no click bindings
    app.badge_dry = badge_dry

    # --- read-only trading status (FSM + policy) ---
    if not hasattr(app, "var_trade_status"):
        app.var_trade_status = tk.StringVar(value="FSM: n/a")

    # --- read-only explainability line for START/STOP + SIM/REAL + SAFE ---
    if not hasattr(app, "var_trade_explain"):
        app.var_trade_explain = tk.StringVar(value="AUTOSIM: n/a")

    # --- chart timeframe (Candles v2) ---
    if not hasattr(app, "var_chart_timeframe"):
        app.var_chart_timeframe = tk.StringVar(value="1m")

    # --- UI toggles: Indicators / RSI / MACD (session-only, READ-ONLY) ---
    def _env_bool(name: str, default: bool) -> bool:
        raw = str(os.environ.get(name, "")).strip().lower()
        if raw == "":
            return bool(default)
        return raw not in ("0", "false", "no", "off")

    # Master default: MB_UI_CHART_INDICATORS
    base_on = _env_bool("MB_UI_CHART_INDICATORS", True)

    # Per-indicator defaults can be overridden by env
    rsi_on_default = _env_bool("MB_UI_ENABLE_RSI", base_on)
    macd_on_default = _env_bool("MB_UI_ENABLE_MACD", base_on)

    if not hasattr(app, "var_chart_rsi_on"):
        app.var_chart_rsi_on = tk.BooleanVar(value=bool(rsi_on_default))
    if not hasattr(app, "var_chart_macd_on"):
        app.var_chart_macd_on = tk.BooleanVar(value=bool(macd_on_default))

    # Keep old var for compatibility (not authoritative if MIX)
    if not hasattr(app, "var_chart_indicators_on"):
        app.var_chart_indicators_on = tk.BooleanVar(value=bool(base_on))

    if not hasattr(app, "var_chart_indicators_label"):
        app.var_chart_indicators_label = tk.StringVar(value="Indicators: ON")
    if not hasattr(app, "var_chart_rsi_label"):
        app.var_chart_rsi_label = tk.StringVar(value="RSI: ON")
    if not hasattr(app, "var_chart_macd_label"):
        app.var_chart_macd_label = tk.StringVar(value="MACD: ON")

    # --- UI toggle: Render mode (FULL/LIGHT) (session-only, READ-ONLY) ---
    if not hasattr(app, "var_chart_render_mode"):
        raw_mode = str(os.environ.get("MB_UI_CHART_RENDER_MODE", "FULL")).strip().upper()
        raw_mode = "LIGHT" if raw_mode in ("LIGHT", "L") else "FULL"
        app.var_chart_render_mode = tk.StringVar(value=raw_mode)

    if not hasattr(app, "var_chart_render_label"):
        try:
            m = str(getattr(app, "var_chart_render_mode").get() or "").strip().upper()
        except Exception:
            m = "FULL"
        m = "LIGHT" if m == "LIGHT" else "FULL"
        app.var_chart_render_label = tk.StringVar(value=f"Render: {m}")

    # Статус переносим в ОТДЕЛЬНУЮ строку под кнопками.
    status_row = ttk.Frame(app, style="Dark.TFrame")
    status_row.pack(fill="x", padx=8, pady=(0, 6))

    # LEFT: explainability (ties START/STOP to mode & safety indicators)
    left_box = ttk.Frame(status_row, style="Dark.TFrame")
    left_box.pack(side="left", fill="x", expand=True, padx=(4, 4))

    lbl_trade_explain = ttk.Label(
        left_box,
        textvariable=app.var_trade_explain,
        style="Dark.TLabel",
        justify="left",
        anchor="w",
    )
    app.lbl_trade_explain = lbl_trade_explain
    app.lbl_trade_explain.pack(side="left", fill="x", expand=True)

    # RIGHT: existing status line (FSM/MODE/age/reason/gate)
    right_box = ttk.Frame(status_row, style="Dark.TFrame")
    right_box.pack(side="right", fill="x", expand=True, padx=(4, 4))

    lbl_trade_status = ttk.Label(
        right_box,
        textvariable=app.var_trade_status,
        style="Dark.TLabel",
        justify="left",
        anchor="e",
    )
    app.lbl_trade_status = lbl_trade_status
    app.lbl_trade_status.pack(side="right", fill="x", expand=True)

    # Wrap по ширине status_row, чтобы весь текст влезал (переносился).
    def _sync_status_wrap(event=None):
        try:
            wl = left_box.winfo_width()
            if wl and wl > 50:
                app.lbl_trade_explain.configure(wraplength=max(50, wl - 10))
        except Exception:
            pass
        try:
            wr = right_box.winfo_width()
            if wr and wr > 50:
                # небольшой запас, чтобы не липло к краям
                app.lbl_trade_status.configure(wraplength=max(50, wr - 10))
        except Exception:
            pass

    left_box.bind("<Configure>", _sync_status_wrap)
    right_box.bind("<Configure>", _sync_status_wrap)
    _sync_status_wrap()

    # --- Explain panel (read-only) — WHY_NOT + GATE_LAST (collapsible) ---
    if not hasattr(app, "var_explain_panel"):
        app.var_explain_panel = tk.StringVar(value="")

    if not hasattr(app, "_explain_collapsed"):
        app._explain_collapsed = True

    if not hasattr(app, "var_explain_toggle"):
        app.var_explain_toggle = tk.StringVar(value="Explain ▸")

    explain_wrap = ttk.Frame(app, style="Dark.TFrame")
    explain_wrap.pack(fill="x", padx=8, pady=(0, 6))

    explain_head = ttk.Frame(explain_wrap, style="Dark.TFrame")
    explain_head.pack(fill="x")

    def _apply_explain_collapse_state():
        try:
            collapsed = bool(getattr(app, "_explain_collapsed", True))
        except Exception:
            collapsed = True

        try:
            app.var_explain_toggle.set("Explain ▸" if collapsed else "Explain ▾")
        except Exception:
            pass

        try:
            if collapsed:
                explain_body.pack_forget()
            else:
                explain_body.pack(fill="x", pady=(2, 0))
        except Exception:
            pass

    def _toggle_explain_panel():
        try:
            app._explain_collapsed = not bool(getattr(app, "_explain_collapsed", True))
        except Exception:
            app._explain_collapsed = True
        _apply_explain_collapse_state()

    btn_explain = ttk.Button(
        explain_head,
        textvariable=app.var_explain_toggle,
        style="Dark.TButton",
        command=_toggle_explain_panel,
    )
    btn_explain.pack(side="left")

    explain_body = ttk.Frame(explain_wrap, style="Dark.TFrame")

    lbl_explain = ttk.Label(
        explain_body,
        textvariable=app.var_explain_panel,
        style="Muted.TLabel",
        justify="left",
        anchor="w",
    )
    app.lbl_explain = lbl_explain
    app.lbl_explain.pack(side="left", fill="x", expand=True, padx=(4, 4))

    def _sync_explain_wrap(event=None):
        try:
            w = explain_wrap.winfo_width()
            if w and w > 50:
                app.lbl_explain.configure(wraplength=max(50, w - 10))
        except Exception:
            pass

    explain_wrap.bind("<Configure>", _sync_explain_wrap)
    _sync_explain_wrap()

    _apply_explain_collapse_state()

    # --- Event spine peek (read-only) — UX: collapse + scroll ---
    # keep var for backward compatibility / fallback
    if not hasattr(app, "var_event_spine"):
        app.var_event_spine = tk.StringVar(value="events: unavailable")

    # collapsed by default to avoid pushing the whole UI down
    if not hasattr(app, "_events_collapsed"):
        app._events_collapsed = True

    events_wrap = ttk.Frame(app, style="Dark.TFrame")
    events_wrap.pack(fill="x", padx=8, pady=(0, 8))

    # header row: toggle + optional short label
    events_head = ttk.Frame(events_wrap, style="Dark.TFrame")
    events_head.pack(fill="x")

    if not hasattr(app, "var_events_toggle"):
        app.var_events_toggle = tk.StringVar(value="Events ▸")

    def _apply_events_collapse_state():
        try:
            collapsed = bool(getattr(app, "_events_collapsed", True))
        except Exception:
            collapsed = True

        try:
            app.var_events_toggle.set("Events ▸" if collapsed else "Events ▾")
        except Exception:
            pass

        try:
            if collapsed:
                events_body.pack_forget()
            else:
                events_body.pack(fill="x", pady=(2, 0))
        except Exception:
            pass

    def _toggle_events_panel():
        try:
            app._events_collapsed = not bool(getattr(app, "_events_collapsed", True))
            app._events_suppressed = False  # explicit user intent → allow redraw
        except Exception:
            app._events_collapsed = True
        _apply_events_collapse_state()

    btn_events = ttk.Button(
        events_head,
        textvariable=app.var_events_toggle,
        style="Dark.TButton",
        command=_toggle_events_panel,
    )
    btn_events.pack(side="left", padx=(0, 8))

    # events view controls (read-only)
    if not hasattr(app, "var_events_count"):
        app.var_events_count = tk.StringVar(value="(0)")

    if not hasattr(app, "_events_autoscroll"):
        app._events_autoscroll = False
    if not hasattr(app, "_events_suppressed"):
        app._events_suppressed = False
    lbl_events_count = ttk.Label(
        events_head,
        textvariable=app.var_events_count,
        style="Dark.TLabel",
    )
    lbl_events_count.pack(side="left", padx=(0, 8))

    def _toggle_events_autoscroll():
        try:
            app._events_autoscroll = not bool(getattr(app, "_events_autoscroll", False))
            app.var_events_autoscroll.set("Auto ▾" if app._events_autoscroll else "Auto ▸")
        except Exception:
            pass

    if not hasattr(app, "var_events_autoscroll"):
        app.var_events_autoscroll = tk.StringVar(
            value="Auto ▸" if not app._events_autoscroll else "Auto ▾"
        )

    btn_autoscroll = ttk.Button(
        events_head,
        textvariable=app.var_events_autoscroll,
        style="Dark.TButton",
        command=_toggle_events_autoscroll,
    )
    btn_autoscroll.pack(side="left", padx=(0, 8))

    def _clear_events_view():
        try:
            app._events_suppressed = True  # suppress redraws until user action

            txt = getattr(app, "txt_events", None)
            if txt is not None:
                try:
                    txt.configure(state="normal")
                except Exception:
                    pass
                try:
                    txt.delete("1.0", "end")
                except Exception:
                    pass
                try:
                    txt.configure(state="disabled")
                except Exception:
                    pass

            if hasattr(app, "var_events_count"):
                app.var_events_count.set("(0)")
        except Exception:
            pass
    btn_clear_events = ttk.Button(
        events_head,
        text="Clear",
        style="Dark.TButton",
        command=_clear_events_view,
    )
    btn_clear_events.pack(side="left")

    # body row: scrollable text (monospace-ish via default, no heavy styling)
    events_body = ttk.Frame(events_wrap, style="Dark.TFrame")

    txt = tk.Text(
        events_body,
        height=4,
        wrap="none",
        borderwidth=0,
        highlightthickness=0,
    )
    # keep UI robust even if theme differs
    try:
        txt.configure(state="disabled")
    except Exception:
        pass

    yscroll = ttk.Scrollbar(events_body, orient="vertical", command=txt.yview)
    txt.configure(yscrollcommand=yscroll.set)

    txt.pack(side="left", fill="x", expand=True)
    yscroll.pack(side="right", fill="y")

    # expose widget for app_ui refresh
    app.txt_events = txt

    _apply_events_collapse_state()

def build_paths_ui(app: Any) -> None:
    """Строит вторую строку с кнопками открытия журналов / data / графиков."""

    box = ttk.Frame(app, style="Dark.TFrame")
    box.pack(fill="x", padx=8, pady=(0, 8))

    ttk.Button(
        box,
        text="Open Journal",
        style="Dark.TButton",
        command=app._cmd_open_trades,
    ).pack(side="left", padx=4)

    ttk.Button(
        box,
        text="SIM Journal",
        style="Dark.TButton",
        command=app._cmd_open_sim_journal,
    ).pack(side="left", padx=4)

    ttk.Button(
        box,
        text="Open Signals",
        style="Dark.TButton",
        command=app._cmd_open_signals,
    ).pack(side="left", padx=4)

    ttk.Button(
        box,
        text="Open LIVE Chart",
        style="Dark.TButton",
        command=app._open_rsi_live_chart,
    ).pack(side="left", padx=4)

    # Candles v2 (read-only): timeframe + open button
    ttk.Label(box, text="TF:", style="Dark.TLabel").pack(side="left", padx=(12, 4))

    tf = ttk.Combobox(
        box,
        textvariable=app.var_chart_timeframe,
        values=("Tick", "1m", "5m", "15m", "1h"),
        width=5,
        state="readonly",
    )
    tf.pack(side="left", padx=4)

    ttk.Button(
        box,
        text="Open LIVE Candles",
        style="Dark.TButton",
        command=app._open_candles_live_chart,
    ).pack(side="left", padx=4)

    ttk.Button(
        box,
        textvariable=app.var_chart_indicators_label,
        style="Dark.TButton",
        command=getattr(app.chart_controller, "toggle_ui_indicators_master", None),
    ).pack(side="left", padx=4)

    ttk.Button(
        box,
        textvariable=app.var_chart_rsi_label,
        style="Dark.TButton",
        command=getattr(app.chart_controller, "toggle_ui_rsi", None),
    ).pack(side="left", padx=4)

    ttk.Button(
        box,
        textvariable=app.var_chart_macd_label,
        style="Dark.TButton",
        command=getattr(app.chart_controller, "toggle_ui_macd", None),
    ).pack(side="left", padx=4)

    ttk.Button(
        box,
        textvariable=app.var_chart_render_label,
        style="Dark.TButton",
        command=getattr(app.chart_controller, "toggle_ui_render_mode", None),
    ).pack(side="left", padx=4)
