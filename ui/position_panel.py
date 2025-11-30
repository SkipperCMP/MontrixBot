try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = None
    ttk = None

from ui.tpsl_status_badge import TpslStatusBadge

class PositionPanel:
    def __init__(self, root, position_provider, tpsl_status_provider):
        self.root = root
        self.position_provider = position_provider
        self.tpsl_status_provider = tpsl_status_provider
        self.tree = None
        self.badge = None

    def mount(self, parent):
        if tk is None: return
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)

        # Top bar with TPSL badge
        top = ttk.Frame(frame)
        top.pack(fill="x")
        self.badge = TpslStatusBadge(top, self.tpsl_status_provider)
        self.badge.mount().pack(side="left", padx=8, pady=6)

        cols = ("symbol", "qty", "entry", "tp", "sl", "tpsl")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", height=10)
        for c in cols:
            self.tree.heading(c, text=c.upper())
            self.tree.column(c, width=100 if c!="symbol" else 120, anchor="center")
        self.tree.pack(fill="both", expand=True)

        self.update_rows()

    def update_rows(self):
        if not self.tree: return
        self.tree.delete(*self.tree.get_children())
        positions = self.position_provider() or {}
        for sym, p in positions.items():
            self.tree.insert("", "end", values=(
                sym, p.get("qty"),
                f'{p.get("entry_price"):.6f}' if p.get("entry_price") else "",
                f'{p.get("tp"):.6f}' if p.get("tp") else "",
                f'{p.get("sl"):.6f}' if p.get("sl") else "",
                "ON" if self.tpsl_status_provider() else "OFF"
            ))
        if self.badge:
            self.badge.refresh()
