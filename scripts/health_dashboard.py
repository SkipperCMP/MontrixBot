
# scripts/health_dashboard.py
import os, tkinter as tk
from tkinter import ttk
import webbrowser

ROOT = os.path.dirname(os.path.dirname(__file__))
RUNTIME = os.path.join(ROOT, "runtime")
LOG = os.path.join(RUNTIME, "health.log")

# Reuse widget
try:
    from ui.health_widget import HealthPanel
except Exception:
    # fallback: local import if user places next to this script
    import sys
    sys.path.insert(0, os.path.join(ROOT, "ui"))
    from health_widget import HealthPanel

def open_runtime():
    # Open runtime folder in explorer
    try:
        os.startfile(RUNTIME)  # Windows
    except Exception:
        import subprocess
        subprocess.Popen(["xdg-open", RUNTIME])

def main():
    os.makedirs(RUNTIME, exist_ok=True)
    root = tk.Tk()
    root.title("MontrixBot Health Dashboard")
    root.geometry("980x520")
    panel = HealthPanel(root, log_path=LOG, refresh_sec=5)
    panel.pack(fill="both", expand=True)
    # Toolbar
    bar = ttk.Frame(root)
    bar.pack(fill="x")
    ttk.Button(bar, text="Open runtime folder", command=open_runtime).pack(side="left", padx=6, pady=6)
    ttk.Label(bar, text=LOG).pack(side="left", padx=6)
    root.mainloop()

if __name__ == "__main__":
    main()
