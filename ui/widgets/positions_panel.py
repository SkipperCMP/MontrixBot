from __future__ import annotations

from typing import Any, Dict, List

import tkinter as tk
from tkinter import ttk


def build_activepos_ui(app: Any) -> None:
    """Панель 'Active position (SIM)'.

    Создаёт:
    - self.btn_reset_sim
    - self.active_box
    и заполняет текстом '— no active positions —'.
    """

    # Если в приложении есть специальный контейнер для панели активных позиций,
    # используем его (ui/app.py: self.frame_active). Иначе — сам app (как в app_step8).
    parent = getattr(app, "frame_active", app)

    frm = ttk.Frame(parent, style="Dark.TFrame")
    frm.pack(fill="x", padx=8, pady=(0, 6))

    header = ttk.Frame(frm, style="Dark.TFrame")
    header.pack(fill="x")

    ttk.Label(
        header,
        text="Active positions (SIM)",
        style="Muted.TLabel",
    ).pack(side="left", anchor="w")

    app.btn_reset_sim = ttk.Button(
        header,
        text="Reset SIM",
        style="Dark.TButton",
        command=app._on_reset_sim,
    )
    app.btn_reset_sim.pack(side="right", padx=(4, 0))

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

    app.active_box.pack(fill="x", pady=(2, 0))
    app._set_active_text("— no active positions —")

def update_active_rows(app: Any, active: List[Dict[str, Any]], last_decisions: Dict[str, Dict[str, Any]]) -> None:
    """
    Рисует таблицу Active positions в текстовом боксе app.active_box,
    но выводит её ЧЕРЕЗ app._set_active_text(...) — чтобы сработали теги цветов.

    active — список позиций (из AUTOSIM или ядра через UIAPI), каждая позиция — dict.
    last_decisions — словарь {SYMBOL: {"action": str, "confidence": float}}.
    """

    # если позиций нет — просто очищаем панель
    if not active:
        try:
            app._set_active_text("— no active positions —")
        except Exception:
            pass
        return

    def _format_hold(hold_days: float) -> str:
        """
        Форматирование времени удержания в виде:
            - HH:MM      (если меньше суток)
            - 1d HH:MM   (если есть целые дни)

        hold_days — число дней (может быть дробным).
        """
        try:
            total_minutes = int(float(hold_days) * 24 * 60)
        except Exception:
            return "--:--"

        if total_minutes < 0:
            total_minutes = 0

        days = total_minutes // (24 * 60)
        rem = total_minutes % (24 * 60)
        hours = rem // 60
        minutes = rem % 60

        if days <= 0:
            # только часы:минуты
            return f"{hours:02d}:{minutes:02d}"
        # дни + часы:минуты
        return f"{days}d {hours:02d}:{minutes:02d}"

    lines: List[str] = []

    # заголовок (ровно тот же, что был в _update_active_from_sim)
    header = "{:<10} {:<6} {:>9} {:>10} {:>10} {:>10} {:>7} {:>10} {:>10} {:>9} {:>5} {:>6}".format(
        "Symbol",
        "Side",
        "Qty",
        "Entry",
        "Last",
        "Value",
        "Pnl%",
        "TP",
        "SL",
        "Hold",
        "Act",
        "Conf",
    )
    lines.append(header)
    lines.append("-" * len(header))

    # строки по позициям
    for pos in active:
        try:
            symbol = str(pos.get("symbol", ""))
            side = str(pos.get("side", ""))[:6]

            qty = float(pos.get("qty", 0.0) or 0.0)
            entry = float(pos.get("entry_price", 0.0) or 0.0)
            last = float(pos.get("current_price", 0.0) or 0.0)

            # базовый PnL% из снапшота (если есть)
            try:
                pnl_pct = float(pos.get("unrealized_pnl_pct", 0.0) or 0.0)
            except Exception:
                pnl_pct = 0.0

            # если движок не посчитал PnL%, считаем сами
            if entry > 0.0 and last > 0.0:
                try:
                    if abs(pnl_pct) < 0.0001:
                        side_u = side.upper()
                        if side_u.startswith("LONG") or side_u == "BUY":
                            pnl_pct = (last - entry) / entry * 100.0
                        elif side_u.startswith("SHORT") or side_u == "SELL":
                            pnl_pct = (entry - last) / entry * 100.0
                except Exception:
                    pass

            # стоимость позиции
            try:
                value = qty * last
            except Exception:
                value = 0.0

            tp = float(pos.get("tp", 0.0) or 0.0)
            sl = float(pos.get("sl", 0.0) or 0.0)
            hold_days = float(pos.get("hold_days", 0.0) or 0.0)
            hold_str = _format_hold(hold_days)

            # --- последние решения ReplaceLogic по этому символу ---
            sym_u = symbol.upper()
            dec = last_decisions.get(sym_u) or {}
            action_raw = str(dec.get("action", "") or "")
            if action_raw == "buy":
                act_str = "B"
            elif action_raw == "close":
                act_str = "C"
            elif action_raw in ("", "none"):
                act_str = "-"
            else:
                act_str = action_raw[:1].upper()

            try:
                conf_val = float(dec.get("confidence", 0.0) or 0.0)
            except Exception:
                conf_val = 0.0

            line = (
                "{:<10} {:<6} {:>9.4f} {:>10.4f} {:>10.4f} "
                "{:>10.2f} {:>7.2f} {:>10.4f} {:>10.4f} {:>9} {:>5} {:>6.2f}"
            ).format(
                symbol,
                side,
                qty,
                entry,
                last,
                value,
                pnl_pct,
                tp,
                sl,
                hold_str,
                act_str,
                conf_val,
            )
            lines.append(line)
        except Exception:
            continue

    # КЛЮЧЕВОЕ: выводим ЧЕРЕЗ _set_active_text, чтобы сработала подсветка
    try:
        app._set_active_text("\n".join(lines))
    except Exception:
        pass

