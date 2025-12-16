# ui/health_widget.py
import tkinter as tk
from tkinter import ttk


class HealthPanel(ttk.Frame):
    """
    UI Isolation:
    - не читаем runtime файлы
    - не импортируем core.*
    - получаем health ТОЛЬКО из snapshot (через UIAPI/StateEngine)
    """

    def __init__(self, master=None, refresh_sec: int = 5, **kw):
        super().__init__(master, **kw)
        self.refresh_sec = max(2, int(refresh_sec))
        self._last_snapshot: dict = {}
        self._build()

    def _build(self) -> None:
        # Header badges
        self.badges = ttk.Frame(self)
        self.badges.pack(fill="x", padx=6, pady=6)

        self.mode_var = tk.StringVar(value="mode=?")
        self.dry_var = tk.StringVar(value="dry=?")
        self.safe_var = tk.StringVar(value="SAFE ?")
        self.age_var = tk.StringVar(value="age: --")

        for var in (self.mode_var, self.dry_var, self.safe_var, self.age_var):
            lbl = ttk.Label(self.badges, textvariable=var, padding=(8, 2))
            lbl.pack(side="left", padx=4)

        # Table
        cols = ("ts", "trades", "open", "close", "active", "last_ts")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=15)
        headers = {
            "ts": "Timestamp (UTC)",
            "trades": "trades.jsonl",
            "open": "OPEN",
            "close": "CLOSE",
            "active": "Active symbols",
            "last_ts": "Last event ts",
        }
        for cid in cols:
            self.tree.heading(cid, text=headers[cid])
            self.tree.column(cid, anchor="w", stretch=True, width=140)
        self.tree.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        # Status line (no paths)
        self.status = tk.StringVar(value="health: snapshot")
        ttk.Label(self, textvariable=self.status).pack(fill="x", padx=6, pady=(0, 6))

    def update_from_snapshot(self, snapshot: dict) -> None:
        self._last_snapshot = snapshot or {}

        # ожидаемый формат: snapshot["health"] или snapshot["health_snapshot"]
        health = {}
        try:
            if isinstance(self._last_snapshot, dict):
                health = (
                    self._last_snapshot.get("health")
                    or self._last_snapshot.get("health_snapshot")
                    or {}
                )
        except Exception:
            health = {}

        entries = health.get("entries") or []
        last_flags = health.get("last_flags") or {}
        last_ts_str = health.get("last_ts_str")

        # status line (no paths)
        self.status.set("health: snapshot")

        # redraw table
        try:
            self.tree.delete(*self.tree.get_children())
        except Exception:
            return

        for item in entries:
            try:
                self.tree.insert(
                    "",
                    "end",
                    values=(
                        item.get("ts", "?"),
                        item.get("trades", "?"),
                        item.get("open", "?"),
                        item.get("close", "?"),
                        item.get("active", "?"),
                        item.get("last_ts", "?"),
                    ),
                )
            except Exception:
                continue

        # badges: mode / Dry-Run / SAFE
        self.mode_var.set(f"Mode: {last_flags.get('mode', '?')}")
        self.dry_var.set(f"Dry-Run: {last_flags.get('dry_run', '?')}")
        self.safe_var.set(f"SAFE {last_flags.get('safe', '?')}")

        # age
        if last_ts_str:
            try:
                import datetime as _dt

                t = _dt.datetime.strptime(last_ts_str, "%Y-%m-%d %H:%M:%S UTC")
                age = (_dt.datetime.utcnow() - t).total_seconds()
                self.age_var.set(f"age: {int(age)}s")
            except Exception:
                self.age_var.set("age: ?")
        else:
            self.age_var.set("age: --")
