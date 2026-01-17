
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from tools.exporting import export_deals_rows

GREEN = "#0a8f08"
RED = "#b00020"
GRAY = "#6b7280"

def _to_float(v):
    try:
        if v is None: 
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).replace('%','').replace('$','').strip()
        if s == "":
            return None
        return float(s)
    except Exception:
        return None

class DealsJournal:
    def __init__(self, parent: tk.Misc):
        self.frame = ttk.Frame(parent)

        # --- toolbar with filters + summary ---
        top = ttk.Frame(self.frame)
        top.pack(fill=tk.X, padx=8, pady=(8,4))

        # Filters (left)
        filt = ttk.Frame(top)
        filt.pack(side=tk.LEFT)

        ttk.Label(filt, text="Symbol").grid(row=0, column=0, padx=(0,4))
        self._sym_var = tk.StringVar()
        sym = ttk.Entry(filt, textvariable=self._sym_var, width=12)
        sym.grid(row=0, column=1, padx=(0,10))
        self._sym_var.trace_add("write", lambda *_: self._apply_filters())

        ttk.Label(filt, text="Tier").grid(row=0, column=2, padx=(0,4))
        self._tier_var = tk.StringVar(value="Any")
        tier = ttk.Combobox(filt, textvariable=self._tier_var, width=6, state="readonly",
                            values=["Any","1","2","3","4","5"])
        tier.grid(row=0, column=3, padx=(0,10))
        tier.bind("<<ComboboxSelected>>", lambda _e: self._apply_filters())

        ttk.Label(filt, text="Action").grid(row=0, column=4, padx=(0,4))
        self._act_var = tk.StringVar(value="Any")
        act = ttk.Combobox(
            filt,
            textvariable=self._act_var,
            width=8,
            state="readonly",
            values=["Any", "CLOSE", "OPEN", "TP", "SL"],
        )
        act.grid(row=0, column=5, padx=(0,10))
        act.bind("<<ComboboxSelected>>", lambda _e: self._apply_filters())

        # --- NEW: PnL / State filter ---
        ttk.Label(filt, text="PnL").grid(row=0, column=6, padx=(0,4))
        self._pnl_var = tk.StringVar(value="Any")
        pnl = ttk.Combobox(
            filt,
            textvariable=self._pnl_var,
            width=8,
            state="readonly",
            values=["Any", "Win", "Loss", "Active", "Closed"],
        )
        pnl.grid(row=0, column=7, padx=(0,10))
        pnl.bind("<<ComboboxSelected>>", lambda _e: self._apply_filters())

        # --- NEW: Date range filters (From/To) ---
        ttk.Label(filt, text="From").grid(row=1, column=0, padx=(0,4), pady=(4,0), sticky="w")
        self._from_var = tk.StringVar(value="")
        frm = ttk.Entry(filt, textvariable=self._from_var, width=18)
        frm.grid(row=1, column=1, padx=(0,10), pady=(4,0), sticky="w")
        self._from_var.trace_add("write", lambda *_: self._apply_filters())

        ttk.Label(filt, text="To").grid(row=1, column=2, padx=(0,4), pady=(4,0), sticky="w")
        self._to_var = tk.StringVar(value="")
        to = ttk.Entry(filt, textvariable=self._to_var, width=18)
        to.grid(row=1, column=3, padx=(0,10), pady=(4,0), sticky="w")
        self._to_var.trace_add("write", lambda *_: self._apply_filters())

        ttk.Label(
            filt,
            text="(YYYY-MM-DD or YYYY-MM-DD HH:MM)",
            foreground=GRAY,
        ).grid(row=1, column=4, columnspan=3, padx=(0,10), pady=(4,0), sticky="w")

        self._clear_btn = ttk.Button(filt, text="Clear", command=self._clear_filters)
        self._clear_btn.grid(row=0, column=8, padx=(0,0))

        # Summary + Heatmap + Export (right)
        self._sum_label = ttk.Label(
            top,
            text="Deals: 0   |   Net: 0.00$   |   Avg: 0.00%",
            foreground=GRAY,
        )
        self._sum_label.pack(side=tk.RIGHT, padx=(0, 12))

        self._heatmap_mode = False
        self._heatmap_var = tk.IntVar(value=0)
        self._heatmap_tags = {}

        self._heatmap_chk = ttk.Checkbutton(
            top,
            text="Heatmap",
            variable=self._heatmap_var,
            command=self._on_toggle_heatmap,
        )
        self._heatmap_chk.pack(side=tk.RIGHT, padx=(4, 4))

        self._export_btn = ttk.Button(top, text="Export", command=self._on_export)
        self._export_btn.pack(side=tk.RIGHT)

        # --- table ---
        cols = (
            "Time",
            "Symbol",
            "Tier",
            "Action",
            "TP",
            "SL",
            "PnL %",
            "PnL $",
            "Trend",
            "Qty",
            "Entry",
            "Exit",
        )
        self.tree = ttk.Treeview(self.frame, columns=cols, show="headings")
        widths = {
            "Time": 140,
            "Symbol": 90,
            "Tier": 60,
            "Action": 80,
            "TP": 80,
            "SL": 80,
            "PnL %": 80,
            "PnL $": 90,
            "Trend": 70,
            "Qty": 80,
            "Entry": 90,
            "Exit": 90,
        }
        for col in cols:
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_by(c, False))
            anchor = tk.CENTER if col in ("Tier","Action","TP","SL") else tk.W
            self.tree.column(col, width=widths[col], anchor=anchor)
        self.tree.tag_configure("profit", foreground=GREEN)
        self.tree.tag_configure("loss", foreground=RED)
        # дополнительные теги для BUY/SELL, Tier и активных сделок
        self.tree.tag_configure("buy", foreground=GREEN)
        self.tree.tag_configure("sell", foreground=RED)
        self.tree.tag_configure("tier1", background="#111827")
        self.tree.tag_configure("tier2", background="#1f2933")
        self.tree.tag_configure("tier3", background="#374151")
        self.tree.tag_configure("tier4", background="#4b5563")
        self.tree.tag_configure("tier5", background="#6b7280")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # data stores
        self._all_rows = []   # full journal
        self._last_rows = []  # filtered view

        # callback для фокуса символа в главном окне
        self._on_focus_symbol = None

        # bind выбора строки
        self.tree.bind("<<TreeviewSelect>>", self._on_row_select)

    def set_focus_callback(self, callback) -> None:
        """Установить колбэк, который будет вызываться при выборе строки журнала.

        callback(symbol: str) -> None
        """
        self._on_focus_symbol = callback

    def _on_row_select(self, _event=None) -> None:
        """Обработчик выбора строки Treeview.

        При наличии callback сообщает главному окну выбранный symbol.
        """
        cb = getattr(self, "_on_focus_symbol", None)
        if cb is None:
            return
        try:
            sel = self.tree.selection()
            if not sel:
                return
            item_id = sel[-1]
            item = self.tree.item(item_id)
            values = item.get("values") or []
            cols = list(self.tree["columns"])
            try:
                sym_idx = cols.index("Symbol")
            except Exception:
                sym_idx = 1  # fallback
            symbol = None
            if 0 <= sym_idx < len(values):
                symbol = values[sym_idx]
            if not symbol:
                return
            cb(str(symbol).strip())
        except Exception:
            # не даём UI падать из-за ошибок в обработчике
            return

    def _on_toggle_heatmap(self):
        """Переключение режима heatmap и полная перерисовка таблицы."""
        self._heatmap_mode = bool(self._heatmap_var.get())
        try:
            self._apply_filters()
        except Exception:
            # не даём UI падать от ошибок heatmap
            pass

    def _ensure_heatmap_tag(self, pnl_pct: float):
        """Создаёт (или переиспользует) тег heatmap для данного PnL%."""
        if pnl_pct is None or pnl_pct == 0:
            return None
        if not getattr(self, "_heatmap_mode", False):
            return None

        pos = pnl_pct > 0
        v = abs(pnl_pct)

        bounds = [1, 2, 4, 7, 10, 15, 25]
        idx = 0
        while idx < len(bounds) and v > bounds[idx]:
            idx += 1
        if idx >= len(bounds):
            idx = len(bounds) - 1

        key = f"heat_pos_{idx}" if pos else f"heat_neg_{idx}"

        if key in self._heatmap_tags:
            return key

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
        color = colors_pos[idx] if pos else colors_neg[idx]

        try:
            self.tree.tag_configure(key, background=color)
            self._heatmap_tags[key] = color
            return key
        except Exception:
            return None

    # --- public API from app ---
    def update(self, rows):
        self._all_rows = list(rows or [])
        self._apply_filters()

    def add_row(self, row):
        self._all_rows.append(row)
        if self._row_matches(row):
            self._insert_row(row)
            self._last_rows.append(row)
            self._recalc_summary()

    # --- internals ---
    def _clear_filters(self):
        self._sym_var.set("")
        self._tier_var.set("Any")
        self._act_var.set("Any")
        if hasattr(self, "_pnl_var"):
            self._pnl_var.set("Any")
        if hasattr(self, "_from_var"):
            self._from_var.set("")
        if hasattr(self, "_to_var"):
            self._to_var.set("")
        self._apply_filters()

    def _is_active_trade(self, r: dict) -> bool:
        """Определяет активную (открытую) сделку по данным строки журнала."""
        exit_val = r.get("exit")
        if exit_val in (None, "", 0, "0"):
            return True
        action = str(r.get("action", "")).upper()
        if action in ("OPEN", "OPEN_LONG", "OPEN_SHORT"):
            return True
        if action in ("BUY", "SELL") and "CLOSE" not in action:
            return True
        return False

    def _parse_time_to_dt(self, v):
        """Пытается распарсить time/ts в datetime (naive local), максимально терпимо."""
        import datetime as _dt

        if v is None or v == "":
            return None

        # epoch seconds/ms
        try:
            if isinstance(v, (int, float)):
                x = float(v)
                if x > 10_000_000_000:  # ms
                    return _dt.datetime.fromtimestamp(x / 1000.0)
                if x > 1_000_000_000:  # sec
                    return _dt.datetime.fromtimestamp(x)
        except Exception:
            pass

        s = str(v).strip()
        if not s:
            return None

        # allow "Z"
        s2 = s.replace("Z", "+00:00")

        # try fromisoformat (supports YYYY-MM-DD, YYYY-MM-DD HH:MM:SS, +00:00)
        try:
            return _dt.datetime.fromisoformat(s2)
        except Exception:
            pass

        # common fallbacks
        fmts = [
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%d.%m.%Y %H:%M",
            "%d.%m.%Y",
        ]
        for f in fmts:
            try:
                return _dt.datetime.strptime(s, f)
            except Exception:
                continue

        return None

    def _parse_filter_dt(self, s: str):
        """Парсит значение фильтра From/To (YYYY-MM-DD или YYYY-MM-DD HH:MM)."""
        return self._parse_time_to_dt(s)

    def _row_matches(self, r: dict) -> bool:
        # symbol filter (substring, case-insensitive)
        sflt = self._sym_var.get().strip().lower()
        if sflt:
            if str(r.get("symbol", "")).lower().find(sflt) == -1:
                return False

        # tier filter
        tflt = self._tier_var.get()
        if tflt != "Any":
            if str(r.get("tier", "")) != tflt:
                return False

        # action filter
        aflt = self._act_var.get()
        if aflt != "Any":
            if str(r.get("action", "")).upper() != aflt.upper():
                return False

        # pnl/state filter
        pflt = self._pnl_var.get() if hasattr(self, "_pnl_var") else "Any"
        pnl_pct = _to_float(r.get("pnl_pct"))
        is_active = self._is_active_trade(r)
        if pflt == "Win":
            if pnl_pct is None or pnl_pct <= 0:
                return False
        elif pflt == "Loss":
            if pnl_pct is None or pnl_pct >= 0:
                return False
        elif pflt == "Active":
            if not is_active:
                return False
        elif pflt == "Closed":
            if is_active:
                return False

        # date range filter
        if hasattr(self, "_from_var") and self._from_var.get().strip():
            dt_from = self._parse_filter_dt(self._from_var.get().strip())
            if dt_from is not None:
                dt_row = self._parse_time_to_dt(r.get("time") or r.get("ts") or "")
                if dt_row is None or dt_row < dt_from:
                    return False

        if hasattr(self, "_to_var") and self._to_var.get().strip():
            dt_to = self._parse_filter_dt(self._to_var.get().strip())
            if dt_to is not None:
                dt_row = self._parse_time_to_dt(r.get("time") or r.get("ts") or "")
                if dt_row is None or dt_row > dt_to:
                    return False

        return True

    def _apply_filters(self):
        self.tree.delete(*self.tree.get_children())
        self._last_rows = []
        for r in self._all_rows:
            if self._row_matches(r):
                self._insert_row(r)
                self._last_rows.append(r)
        self._recalc_summary()

    def _insert_row(self, r):
        def _fmt_num(v):
            if v in (None, ""):
                return ""
            if isinstance(v, (int, float)):
                return f"{v:.3f}"
            return str(v)

        def _spark(v, is_active: bool):
            """Мини-спарклайн по PnL% + маркер активной сделки."""
            v_f = _to_float(v)
            if v_f is None:
                return "●" if is_active else ""
            blocks = "▁▂▃▄▅▆▇"
            av = min(abs(v_f), 35.0)
            idx = int((av / 35.0) * (len(blocks) - 1))
            blk = blocks[idx] if 0 <= idx < len(blocks) else blocks[-1]
            if v_f > 0:
                return f"+{blk}"
            if v_f < 0:
                return f"-{blk}"
            return blk

        tags = []

        # PnL-based coloring (profit/loss)
        pnl_pct = _to_float(r.get("pnl_pct"))
        if pnl_pct is not None:
            try:
                if pnl_pct < 0:
                    tags.append("loss")
                else:
                    tags.append("profit")
            except Exception:
                pass
        else:
            # если PnL ещё нет — подсветим по действию BUY/SELL
            action = str(r.get("action", "")).upper()
            if "BUY" in action:
                tags.append("buy")
            elif "SELL" in action:
                tags.append("sell")

        # Tier-based background
        tier_val = r.get("tier")
        try:
            t_int = int(tier_val)
            if 1 <= t_int <= 5:
                tags.append(f"tier{t_int}")
        except Exception:
            pass

        # Active (открытая) сделка: нет exit или явно OPEN
        exit_val = r.get("exit")
        is_active = False
        if exit_val in (None, "", 0, "0"):
            is_active = True
        else:
            action = str(r.get("action", "")).upper()
            if action in ("OPEN", "OPEN_LONG", "OPEN_SHORT"):
                is_active = True
            elif action in ("BUY", "SELL") and "CLOSE" not in action:
                is_active = True

        # Heatmap-tag по PnL% (если включён режим)
        if pnl_pct is not None:
            tag = self._ensure_heatmap_tag(pnl_pct)
            if tag:
                tags.append(tag)

        values = (
            r.get("time", ""),
            r.get("symbol", ""),
            r.get("tier", ""),
            r.get("action", ""),
            _fmt_num(r.get("tp")),
            _fmt_num(r.get("sl")),
            r.get("pnl_pct", ""),
            r.get("pnl_abs", ""),
            _spark(r.get("pnl_pct"), is_active),
            _fmt_num(r.get("qty")),
            _fmt_num(r.get("entry")),
            _fmt_num(r.get("exit")),
        )
        item_id = self.tree.insert("", tk.END, values=values, tags=tuple(tags))
        try:
            # авто-скролл к последней строке
            self.tree.yview_moveto(1.0)
        except Exception:
            pass
        return item_id

    def _recalc_summary(self):
        n = len(self._last_rows)
        net = 0.0
        cnt_pct = 0
        sum_pct = 0.0
        wins = 0
        closed = 0
        best = None
        worst = None
        dur_sum = 0.0
        dur_count = 0
        max_dur = None
        min_dur = None

        for r in self._last_rows:
            v_abs = _to_float(r.get("pnl_abs"))
            if v_abs is not None:
                net += v_abs

            v_pct = _to_float(r.get("pnl_pct"))
            if v_pct is not None:
                sum_pct += v_pct
                cnt_pct += 1
                closed += 1
                if v_pct > 0:
                    wins += 1
                if best is None or v_pct > best:
                    best = v_pct
                if worst is None or v_pct < worst:
                    worst = v_pct

            dur = r.get("duration_sec")
            if dur is None:
                dur = r.get("duration")
            d = _to_float(dur)
            if d is not None and d > 0:
                dur_sum += d
                dur_count += 1
                if max_dur is None or d > max_dur:
                    max_dur = d
                if min_dur is None or d < min_dur:
                    min_dur = d

        avg = (sum_pct / cnt_pct) if cnt_pct > 0 else 0.0
        winrate = (wins / closed * 100.0) if closed > 0 else 0.0
        losses = closed - wins

        def _fmt_dur(sec_val):
            if sec_val is None or sec_val <= 0:
                return "n/a"
            sec_val = int(sec_val)
            mins, secs = divmod(sec_val, 60)
            hours, mins = divmod(mins, 60)
            if hours > 0:
                return f"{hours}h {mins}m"
            if mins > 0:
                return f"{mins}m {secs}s"
            return f"{secs}s"

        if dur_count > 0:
            avg_dur_sec = dur_sum / dur_count
        else:
            avg_dur_sec = None

        avg_dur_str = _fmt_dur(avg_dur_sec)
        longest_str = _fmt_dur(max_dur)
        shortest_str = _fmt_dur(min_dur)

        best_str = f"{best:+.2f}%" if best is not None else "n/a"
        worst_str = f"{worst:+.2f}%" if worst is not None else "n/a"

        color = GRAY
        if net > 1e-12:
            color = GREEN
        elif net < -1e-12:
            color = RED

        text = (
            f"Deals: {n}   |   Net: {net:.2f}$   |   Avg: {avg:.2f}%   |   "
            f"Win: {wins}/{closed} ({winrate:.1f}%)   |   P/L: {wins}/{losses}   |   "
            f"Best: {best_str}   |   Worst: {worst_str}   |   "
            f"AvgDur: {avg_dur_str}   |   Long: {longest_str}   |   Short: {shortest_str}"
        )
        self._sum_label.configure(text=text, foreground=color)

    def _sort_by(self, col, descending):
        col_idx = list(self.tree["columns"]).index(col)
        data = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        try:
            key=lambda t: float(str(t[0]).replace('%','').replace('$',''))
            data.sort(key=key, reverse=descending)
        except Exception:
            data.sort(reverse=descending)
        for idx, item in enumerate(data):
            self.tree.move(item[1], "", idx)
        self.tree.heading(col, command=lambda c=col: self._sort_by(c, not descending))

    def _on_export(self):
        try:
            if not self._last_rows:
                messagebox.showinfo("Export", "Журнал пуст, экспортировать нечего.")
                return
            paths = export_deals_rows(
                self._last_rows,
                out_dir="exports",
                csv_dir="exports/csv",
                json_dir="exports/json",
                xlsx_dir="exports/xlsx",
            )
            msg = f"Экспорт выполнен:\nCSV: {paths.get('csv')}\nJSON: {paths.get('json')}"
            xlsx_path = paths.get("xlsx")
            if xlsx_path:
                msg += f"\nXLSX: {xlsx_path}"
            else:
                msg += "\nXLSX: не создан (нет openpyxl?)"
            messagebox.showinfo("Export", msg)
        except Exception as e:
            messagebox.showerror("Export error", str(e))
            
        # --- router-биндинг от снапшота ядра ---
    def update_from_snapshot(self, snapshot: dict) -> None:
        """Обновить журнал сделок по снапшоту UIAPI/StateEngine.

        Приоритет:
        1) snapshot["deals_rows"] (TradeBook);
        2) fallback: snapshot["trades_recent"] (старый буфер AUTOSIM/UIAPI).
        """
        if not isinstance(snapshot, dict):
            return

        rows = None

        # NEW: сначала пробуем deals_rows из TradeBook
        try:
            dr = snapshot.get("deals_rows")
            if isinstance(dr, list):
                rows = dr
        except Exception:
            rows = None

        # fallback: старый формат trades_recent
        if rows is None:
            try:
                tr = snapshot.get("trades_recent")
                if isinstance(tr, list):
                    rows = tr
            except Exception:
                rows = None

        if not rows:
            return

        self.update(rows)


