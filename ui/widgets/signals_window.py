from __future__ import annotations

from typing import Callable, Any

import time

import tkinter as tk
from tkinter import messagebox
from tkinter import ttk


def open_signals_window(
    parent: tk.Misc,
    uiapi_getter: Callable[[], Any],
    limit: int = 500,
) -> None:
    """
    UI-only window: Signals history.

    Behavior preserved from App._cmd_open_signals in ui/app_step9.py:
    - Prefer UIAPI buffer (api.get_recent_signals_tail)
    - Fallback: legacy file-based history (deprecated)
    - Show last ~500 (default) newest-first
    - Optional heatmap RSI mode (checkbox)
    """

    # Prefer UIAPI buffer (no direct runtime file reads from UI)
    records: list[dict] = []
    try:
        api = uiapi_getter()
        if api is not None and hasattr(api, "get_recent_signals_tail"):
            records = api.get_recent_signals_tail(limit=limit) or []
    except Exception:
        records = []

    if not records:
        messagebox.showinfo("Signals", "No signals to display yet.")
        return

    win = tk.Toplevel(parent)
    win.title("MontrixBot — Signals history")
    win.geometry("900x400")
    try:
        win.configure(bg="#0f1216")  # тёмный фон окна
    except Exception:
        pass

    cols = ("ts", "symbol", "side", "rsi", "macd", "macd_sig", "priority", "reason")
    headers = {
        "ts": "Time",
        "symbol": "Symbol",
        "side": "Side",
        "rsi": "RSI",
        "macd": "MACD",
        "macd_sig": "MACD sig",
        "reason": "Reason",
        "priority": "Prio",
    }
    widths = {
        "ts": 150,
        "symbol": 80,
        "side": 70,
        "rsi": 60,
        "macd": 80,
        "macd_sig": 80,
        "reason": 380,
        "priority": 80,
    }

    # локальный стиль под тёмную тему
    style = ttk.Style(win)
    try:
        style.configure(
            "Signals.Treeview",
            background="#171B21",
            fieldbackground="#171B21",
            foreground="#E6EAF2",
            rowheight=20,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Signals.Treeview.Heading",
            background="#111827",
            foreground="#E6EAF2",
            font=("Segoe UI", 9, "bold"),
        )
    except Exception:
        # если что-то не поддерживается — просто остаёмся на дефолтном стиле
        pass

    # верхняя панель: заголовок + чекбокс heatmap
    top = ttk.Frame(win)
    top.pack(side="top", fill="x")

    ttk.Label(
        top,
        text=f"Signals (last {len(records)} records)",
    ).pack(side="left", padx=(10, 0), pady=4)

    heatmap_var = tk.IntVar(value=0)
    ttk.Checkbutton(
        top,
        text="Heatmap RSI",
        variable=heatmap_var,
    ).pack(side="right", padx=(0, 12), pady=4)

    # основное дерево
    tree = ttk.Treeview(
        win,
        columns=cols,
        show="headings",
        style="Signals.Treeview",
    )
    tree.pack(fill="both", expand=True, side="left")

    vsb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")

    numeric_right = {"rsi", "macd", "macd_sig"}
    center_cols = {"symbol", "side"}

    for cid in cols:
        heading_text = headers.get(cid, cid.upper())
        tree.heading(cid, text=heading_text)

        if cid in numeric_right:
            anchor = "e"       # числа вправо
        elif cid in center_cols:
            anchor = "center"  # символ/сторона по центру
        else:
            anchor = "w"       # время и reason влево

        tree.column(
            cid,
            width=widths.get(cid, 80),
            anchor=anchor,
            stretch=True,
        )

    def _fmt_float(val: object, pattern: str = "{:.4f}") -> str:
        try:
            return pattern.format(float(val))
        except Exception:
            return ""

    def _to_float(val: object) -> float | None:
        try:
            return float(val)
        except Exception:
            return None

    # палитры, согласованные с журналом сделок
    colors_pos = [
        "#052e16",
        "#064e3b",
        "#047857",
        "#059669",
        "#10b981",
        "#34d399",
        "#6ee7b7",
    ]
    colors_neg = [
        "#3b0d0c",
        "#5c1a15",
        "#7f2318",
        "#a52a1f",
        "#cc3d2b",
        "#e2583b",
        "#ff7043",
    ]
    heatmap_tags: dict[str, str] = {}

    def _ensure_heatmap_tag_from_rsi(rsi_val: float | None) -> str | None:
        """Подбирает/создаёт тег heatmap по RSI.

        • RSI < 30  — зона перепроданности (зелёная шкала)
        • RSI > 70  — зона перекупленности (красная шкала)
        • иначе     — без подсветки
        """
        if not heatmap_var.get():
            return None
        if rsi_val is None:
            return None

        if rsi_val < 30.0:
            palette = colors_pos
            delta = 30.0 - rsi_val
            key_prefix = "rsi_low"
        elif rsi_val > 70.0:
            palette = colors_neg
            delta = rsi_val - 70.0
            key_prefix = "rsi_high"
        else:
            return None

        bounds = [1, 2, 4, 7, 10, 15, 25]
        idx = 0
        while idx < len(bounds) and delta > bounds[idx]:
            idx += 1
        if idx >= len(bounds):
            idx = len(bounds) - 1

        key = f"{key_prefix}_{idx}"
        if key in heatmap_tags:
            return key

        color = palette[idx]
        try:
            tree.tag_configure(key, background=color)
            heatmap_tags[key] = color
            return key
        except Exception:
            return None

    def _apply_heatmap_to_all() -> None:
        """Пересчитать heatmap-теги для всех строк."""
        for item_id in tree.get_children(""):
            item = tree.item(item_id)
            values = item.get("values") or []
            tags: list[str] = []
            rsi_str = values[3] if len(values) > 3 else ""
            rsi_val = _to_float(rsi_str)
            tag = _ensure_heatmap_tag_from_rsi(rsi_val)
            if tag:
                tags.append(tag)
            tree.item(item_id, tags=tuple(tags))

    # привязка чекбокса к пересчёту heatmap
    def _on_heatmap_toggle() -> None:
        _apply_heatmap_to_all()

    heatmap_var.trace_add("write", lambda *_: _on_heatmap_toggle())

    def _fmt_ts(ts) -> str:
        """
        TS can be:
          - seconds (int/float)
          - milliseconds (int/float, very large)
          - numeric string
        Windows localtime() may raise OSError on out-of-range values.
        """
        if ts is None:
            return ""
        try:
            # numeric string
            if isinstance(ts, str):
                s = ts.strip()
                if s.isdigit():
                    ts = int(s)
                else:
                    return s

            if isinstance(ts, (int, float)):
                v = float(ts)

                # Heuristic: treat big values as ms
                # 1e12 ~ 2001-09 in ms; anything above is definitely ms
                if v >= 1e12:
                    v = v / 1000.0
                # also treat "future-ish" seconds as ms (safety net)
                elif v >= 2e10:
                    v = v / 1000.0

                # clamp to avoid Windows OSError for extreme ranges
                if v < 0:
                    v = 0.0

                try:
                    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(v))
                except Exception:
                    return str(int(v))
        except Exception:
            pass

        return str(ts)

    # свежие записи показываем сверху
    for obj in reversed(records):
        ts_str = _fmt_ts(obj.get("ts"))
        sym = str(obj.get("symbol") or "")
        side = str(obj.get("side") or obj.get("status") or "")
        rsi = _fmt_float(obj.get("rsi"), "{:.2f}")
        macd = _fmt_float(obj.get("macd"))
        macd_sig = _fmt_float(obj.get("macd_sig") if obj.get("macd_sig") is not None else obj.get("macd_signal"))
        scout_note = obj.get("scout_note") if isinstance(obj, dict) else None
        prio = ""

        # priority may live either on top-level or inside scout_note
        try:
            if isinstance(obj, dict) and obj.get("priority"):
                prio = str(obj.get("priority"))
            elif isinstance(scout_note, dict) and scout_note.get("priority"):
                prio = str(scout_note.get("priority"))
        except Exception:
            prio = ""

        reason = str(obj.get("reason") or obj.get("note") or "")
        values = (ts_str, sym, side, rsi, macd, macd_sig, prio, reason)
        item_id = tree.insert("", 0, values=values)

        # apply heatmap tag per-row (if enabled)
        tag = _ensure_heatmap_tag_from_rsi(_to_float(rsi))
        if tag:
            try:
                tree.item(item_id, tags=(tag,))
            except Exception:
                pass

    # первая отрисовка heatmap если чекбокс уже включён
    try:
        _apply_heatmap_to_all()
    except Exception:
        pass
