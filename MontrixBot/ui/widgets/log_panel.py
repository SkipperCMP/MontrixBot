from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk


def build_log_ui(app: Any, StatusBar: Any, parent: Any = None) -> None:
    """Основная лог-панель + LastSig + StatusBar.

    Создаёт на `app`:
    - label_last_sig  — строка с последним сигналом
    - log             — tk.Text для основного лога
    - status_bar      — экземпляр StatusBar (если класс передан)
    """
    host = parent if parent is not None else app

    # Корневой фрейм лога
    frm = ttk.Frame(host, style="Log.TFrame")
    frm.pack(fill="both", expand=True, padx=8, pady=(4, 8))

    # ------------------------------------------------------------------ top row: Last signal + buttons
    top = ttk.Frame(frm, style="Log.TFrame")
    top.pack(fill="x", pady=(0, 4))

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


    # --- Signal line aggregator (UI-only) ---
    # Старый updater обновляет 4 разных label_*.
    # Мы собираем их в одну строку над логом, не ломая совместимость.
    class _SignalLineAgg:
        def __init__(self, out_label: ttk.Label) -> None:
            self._out = out_label
            self._data = {
                "signal": None,   # e.g. "BUY 0.33"
                "reco": None,     # e.g. "BUY 0.31"
                "trend": None,    # e.g. "DOWN"
                "macd": None,     # e.g. "bullish (+0.056)"
                "rsi": None,      # e.g. "55.7"
            }

        def _render(self) -> None:
            parts = []

            if self._data["signal"]:
                parts.append(f"Signal: {self._data['signal']}")
            if self._data["reco"]:
                parts.append(f"Rec: {self._data['reco']}")
            if self._data["trend"]:
                parts.append(f"trend: {self._data['trend']}")
            if self._data["macd"]:
                parts.append(f"MACD: {self._data['macd']}")
            if self._data["rsi"]:
                parts.append(f"RSI: {self._data['rsi']}")

            text = " | ".join(parts) if parts else "Signal: n/a"
            try:
                self._out.configure(text=text)
            except Exception:
                pass

        def set_part(self, key: str, text: str) -> None:
            t = text.strip()

            # Signal / Rec
            if key in ("signal", "reco"):
                # примеры: "Signal BUY [0.33]", "Rec: BUY ↑ 0.31"
                for token in ("Signal", "Rec", ":", "↑", "[", "]"):
                    t = t.replace(token, "")
                self._data[key] = " ".join(t.split()[:2])

            # MACD
            elif key == "macd":
                # примеры: "MACD bullish", "MACD: +0.0566"
                t = t.replace("MACD", "").replace(":", "").strip()
                self._data["macd"] = t

            # RSI
            elif key == "rsi":
                # примеры: "RSI neutral", "RSI: 55.7"
                t = t.replace("RSI", "").replace(":", "").strip()
                self._data["rsi"] = t

            self._render()

    class _ProxyLabel:
        def __init__(self, agg: _SignalLineAgg, key: str) -> None:
            self._agg = agg
            self._key = key

        def configure(self, **kwargs):
            text = kwargs.get("text")
            if isinstance(text, str):
                self._agg.set_part(self._key, text)

        # некоторые места используют .config()
        def config(self, **kwargs):
            return self.configure(**kwargs)

    # Создаём единую строку над логом (слева), кнопка Clear log справа остаётся.
    # top — это верхний ряд лог-панели.
    sig_label = ttk.Label(
        top,
        text="Signal: n/a | Rec: n/a | MACD: n/a | RSI: n/a",
        style="Muted.TLabel",
        anchor="w",
    )
    sig_label.pack(side="left", padx=(4, 8))

    agg = _SignalLineAgg(sig_label)

    # Подменяем старые label_* на прокси, чтобы updater продолжил работать.
    app.label_signal = _ProxyLabel(agg, "signal")
    app.label_reco = _ProxyLabel(agg, "reco")
    app.label_macd = _ProxyLabel(agg, "macd")
    app.label_rsi = _ProxyLabel(agg, "rsi")

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

    # --- HealthPanel (disabled) ---
    app.health_panel = None

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
