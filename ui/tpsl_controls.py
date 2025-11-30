try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = None
    ttk = None

import json, os

class TpslControls:
    def __init__(self, parent, on_changed=None):
        self.parent = parent
        self.on_changed = on_changed or (lambda: None)
        self._widgets = {}

    def mount(self):
        if tk is None:
            return None
        frm = ttk.Frame(self.parent)
        # Mode selector
        ttk.Label(frm, text="TPSL Mode:").grid(row=0, column=0, padx=6, pady=4, sticky="w")
        mode = ttk.Combobox(frm, values=["dynamic","static"], state="readonly", width=9)
        mode.grid(row=0, column=1, padx=4, pady=4, sticky="w")
        mode.set(self._read("mode","dynamic"))
        self._widgets["mode"] = mode

        # Base pct
        ttk.Label(frm, text="Base %:").grid(row=0, column=2, padx=6, pady=4, sticky="e")
        base = ttk.Entry(frm, width=6)
        base.insert(0, str(self._read(("dynamic","base_pct"), 0.35)))
        base.grid(row=0, column=3, padx=4, pady=4)
        self._widgets["base"] = base

        # Min/Max pct
        ttk.Label(frm, text="Min %:").grid(row=0, column=4, padx=6, pady=4, sticky="e")
        vmin = ttk.Entry(frm, width=6)
        vmin.insert(0, str(self._read(("dynamic","min_pct"), 0.2)))
        vmin.grid(row=0, column=5, padx=4, pady=4)
        self._widgets["min"] = vmin

        ttk.Label(frm, text="Max %:").grid(row=0, column=6, padx=6, pady=4, sticky="e")
        vmax = ttk.Entry(frm, width=6)
        vmax.insert(0, str(self._read(("dynamic","max_pct"), 1.0)))
        vmax.grid(row=0, column=7, padx=4, pady=4)
        self._widgets["max"] = vmax

        # Window
        ttk.Label(frm, text="Win:").grid(row=0, column=8, padx=6, pady=4, sticky="e")
        win = ttk.Entry(frm, width=6)
        win.insert(0, str(int(self._read(("dynamic","vol_window"), 50))))
        win.grid(row=0, column=9, padx=4, pady=4)
        self._widgets["win"] = win

        # Apply button
        btn = ttk.Button(frm, text="Apply", command=self.apply)
        btn.grid(row=0, column=10, padx=8, pady=4)
        self._widgets["apply"] = btn

        return frm

    def _read(self, key, default=None):
        cfg = self._load()
        tp = cfg.get("tpsl_autoloop", {})
        if isinstance(key, tuple):
            cur = tp
            for k in key:
                if not isinstance(cur, dict):
                    return default
                cur = cur.get(k, {})
            return cur if cur is not None else default
        return tp.get(key, default)

    def _load(self):
        p = "runtime/settings.json"
        if not os.path.exists(p):
            return {}
        try:
            with open(p,"r",encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self, cfg):
        try:
            with open("runtime/settings.json","w",encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def apply(self):
        cfg = self._load()
        tp = cfg.setdefault("tpsl_autoloop", {})
        tp["mode"] = self._widgets["mode"].get().lower()
        dyn = tp.setdefault("dynamic", {})
        def _f(v, dv):
            try:
                return float(v)
            except Exception:
                return dv
        dyn["base_pct"] = _f(self._widgets["base"].get(), 0.35)
        dyn["min_pct"]  = _f(self._widgets["min"].get(), 0.2)
        dyn["max_pct"]  = _f(self._widgets["max"].get(), 1.0)
        try:
            dyn["vol_window"] = int(float(self._widgets["win"].get()))
        except Exception:
            dyn["vol_window"] = 50
        self._save(cfg)
        self.on_changed()
