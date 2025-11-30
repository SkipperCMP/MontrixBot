
# ui/health_widget.py
import os, json, time
import tkinter as tk
from tkinter import ttk

DEFAULT_LOG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "runtime", "health.log")

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

    def _parse_line(self, line: str):
        # Expected format produced by health_monitor.py
        # 2025-11-09 17:00:00 UTC | mode=REAL dry_run=True safe=ON | trades=553B open=2 close=2 active=[] last_ts=...
        parts = [p.strip() for p in line.strip().split("|")]
        if len(parts) < 3:
            return None
        ts = parts[0]
        L = parts[2]  # right side
        kv = {}
        for token in L.split():
            if "=" in token:
                k,v = token.split("=",1)
                kv[k]=v
        trades = kv.get("trades","?")
        open_ = kv.get("open","?")
        close = kv.get("close","?")
        active = kv.get("active","?")
        last_ts = kv.get("last_ts","?")
        # middle
        mid = parts[1]
        flags = {}
        for token in mid.split():
            if "=" in token:
                k,v = token.split("=",1)
                flags[k]=v
        return ts, trades, open_, close, active, last_ts, flags

    def _refresh(self):
        lines = []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()[-200:]  # tail
        except FileNotFoundError:
            self.status.set(f"log: {self.log_path} (not found — run run_health.cmd)")
            return
        except Exception as e:
            self.status.set(f"error reading log: {e}")
            return

        # Clear table
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        last_flags = {}
        last_ts_str = None
        for ln in lines:
            parsed = self._parse_line(ln)
            if not parsed: 
                continue
            ts, trades, open_, close, active, last_ts, flags = parsed
            self.tree.insert("", "end", values=(ts, trades, open_, close, active, last_ts))
            last_flags = flags
            last_ts_str = ts

        # Update badges
        mode = last_flags.get("mode","?")
        dry = last_flags.get("dry_run","?")
        safe = last_flags.get("safe","?")
        self.mode_var.set(f"Mode: {mode}")
        self.dry_var.set(f"Dry-Run: {dry}")
        self.safe_var.set(f"SAFE {safe}")
        # age calc
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
