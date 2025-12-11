
# ui/health_widget.py
import os
import tkinter as tk
from tkinter import ttk

from core.health_api import load_health_snapshot

DEFAULT_LOG = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "runtime",
    "health.log",
)

class HealthPanel(ttk.Frame):
    def __init__(self, master=None, log_path: str = None, refresh_sec: int = 5, **kw):
        super().__init__(master, **kw)
        self.log_path = log_path or DEFAULT_LOG
        self.refresh_sec = max(2, int(refresh_sec))
        self._build()
        self._schedule_refresh()

    def _build(self):
        # Header badges
        self.badges = ttk.Frame(self)
        self.badges.pack(fill="x", padx=6, pady=6)

        self.mode_var = tk.StringVar(value="mode=?")
        self.dry_var  = tk.StringVar(value="dry=?")
        self.safe_var = tk.StringVar(value="SAFE ?")
        self.age_var  = tk.StringVar(value="age: --")

        for var in (self.mode_var, self.dry_var, self.safe_var, self.age_var):
            lbl = ttk.Label(self.badges, textvariable=var, padding=(8,2))
            lbl.pack(side="left", padx=4)

        # Table
        cols = ("ts","trades","open","close","active","last_ts")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=15)
        headers = {
            "ts": "Timestamp (UTC)",
            "trades": "trades.jsonl",
            "open": "OPEN",
            "close": "CLOSE",
            "active": "Active symbols",
            "last_ts": "Last event ts"
        }
        for cid in cols:
            self.tree.heading(cid, text=headers[cid])
            self.tree.column(cid, anchor="w", stretch=True, width=140)
        self.tree.pack(fill="both", expand=True, padx=6, pady=(0,6))

        # Status line
        self.status = tk.StringVar(value=f"log: {self.log_path}")
        ttk.Label(self, textvariable=self.status).pack(fill="x", padx=6, pady=(0,6))

    def _schedule_refresh(self):
        self._refresh()
        self.after(self.refresh_sec * 1000, self._schedule_refresh)

    def _refresh(self):
        """Обновляет таблицу health и бейджи, используя core.health_api."""
        try:
            data = load_health_snapshot(self.log_path, max_lines=500)
        except Exception as e:
            # любые проблемы HealthAPI не должны ломать UI
            self.status.set(f"error: {e}")
            return

        entries = data.get("entries") or []
        last_flags = data.get("last_flags") or {}
        last_ts_str = data.get("last_ts_str")
        log_path = data.get("log_path") or self.log_path

        # обновляем статусную строку
        self.status.set(f"log: {log_path}")

        # перерисовываем таблицу
        try:
            self.tree.delete(*self.tree.get_children())
        except Exception:
            return

        for item in entries:
            try:
                ts = item.get("ts", "?")
                trades = item.get("trades", "?")
                open_ = item.get("open", "?")
                close = item.get("close", "?")
                active = item.get("active", "?")
                last_ts = item.get("last_ts", "?")
                self.tree.insert(
                    "",
                    "end",
                    values=(ts, trades, open_, close, active, last_ts),
                )
            except Exception:
                # одна битая запись не должна ломать остальные
                continue

        # бейджи: mode / Dry-Run / SAFE
        mode = last_flags.get("mode", "?")
        dry = last_flags.get("dry_run", "?")
        safe = last_flags.get("safe", "?")
        self.mode_var.set(f"Mode: {mode}")
        self.dry_var.set(f"Dry-Run: {dry}")
        self.safe_var.set(f"SAFE {safe}")

        # возраст последнего события
        if last_ts_str:
            try:
                # 'YYYY-MM-DD HH:MM:SS UTC'
                import datetime as _dt
                t = _dt.datetime.strptime(last_ts_str, "%Y-%m-%d %H:%M:%S UTC")
                age = (_dt.datetime.utcnow() - t).total_seconds()
                self.age_var.set(f"age: {int(age)}s")
            except Exception:
                self.age_var.set("age: ?")
        else:
            self.age_var.set("age: --")
