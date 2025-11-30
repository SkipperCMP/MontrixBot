import os, sys, json, time
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    import tkinter as tk
    from tkinter import ttk
except Exception as e:
    print("Tkinter is required for this test:", e)
    raise

# Ensure runtime/settings.json exists with tpsl_autoloop.enabled
os.makedirs(os.path.join(ROOT, "runtime"), exist_ok=True)
settings_path = os.path.join(ROOT, "runtime", "settings.json")
try:
    with open(settings_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
except Exception:
    cfg = {}
cfg.setdefault("tpsl_autoloop", {"enabled": True})
with open(settings_path, "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)

from ui.tpsl_status_badge import TpslStatusBadge

def tpsl_enabled():
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            return bool(json.load(f).get("tpsl_autoloop",{}).get("enabled", True))
    except Exception:
        return False

root = tk.Tk()
root.title("TPSL Badge Test")
frm = ttk.Frame(root)
frm.pack(fill="x", padx=8, pady=8)

badge = TpslStatusBadge(frm, tpsl_enabled)
lbl = badge.mount()
if lbl:
    lbl.pack(side="right")

# Toggle button to flip enabled in runtime/settings.json and refresh badge
def toggle():
    with open(settings_path, "r", encoding="utf-8") as f:
        c = json.load(f)
    cur = bool(c.get("tpsl_autoloop",{}).get("enabled", True))
    c.setdefault("tpsl_autoloop", {})["enabled"] = not cur
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)
    badge.refresh()

btn = ttk.Button(frm, text="Toggle TPSL", command=toggle)
btn.pack(side="left")

root.mainloop()
