try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = None
    ttk = None

class TpslStatusBadge:
    def __init__(self, parent, status_provider):
        self.parent = parent
        self.status_provider = status_provider
        self._label = None

    def mount(self):
        if tk is None:
            return None
        self._label = ttk.Label(self.parent, text="TPSL: —", anchor="center")
        try:
            style = ttk.Style()
            style.configure("TPSL.ON.TLabel", foreground="#22c55e", font=("Segoe UI", 12, "bold"))
            style.configure("TPSL.OFF.TLabel", foreground="#ef4444", font=("Segoe UI", 12, "bold"))
        except Exception:
            pass
        self.refresh()
        return self._label

    def refresh(self):
        if not self._label:
            return
        on = bool(self.status_provider())
        self._label.configure(text=f"TPSL: {'ON' if on else 'OFF'}")
        try:
            self._label.configure(style="TPSL.ON.TLabel" if on else "TPSL.OFF.TLabel")
        except Exception:
            pass
