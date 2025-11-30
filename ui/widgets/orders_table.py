
from __future__ import annotations
from typing import List, Dict, Any, Optional
import tkinter as tk
from tkinter import ttk

class OrdersTable:
    """Отображение ордеров (агрегированных)."""
    COLS = ("order_id", "symbol", "side", "price", "qty", "filled_qty", "status")

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.Frame(parent)
        self.tree = ttk.Treeview(self.frame, columns=self.COLS, show="headings", height=18)
        headers = ["ID","Symbol","Side","Price","Qty","Filled","Status"]
        for c, title in zip(self.COLS, headers):
            self.tree.heading(c, text=title)
            anchor = tk.E if c in ("price","qty","filled_qty") else tk.W
            self.tree.column(c, width=120, anchor=anchor)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb = ttk.Scrollbar(self.frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set); vsb.pack(side=tk.RIGHT, fill=tk.Y)

    def update(self, rows: List[Dict[str, Any]]) -> None:
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            self.tree.insert("", tk.END, values=(
                r.get("order_id","—"),
                r.get("symbol","—"),
                r.get("side",""),
                r.get("price",0.0),
                r.get("qty",0.0),
                r.get("filled_qty",0.0),
                r.get("status",""),
            ))
