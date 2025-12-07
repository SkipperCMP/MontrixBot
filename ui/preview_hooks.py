# Optional small helpers for UI integration without heavy edits.

def apply_preview_colors(lbl_price, lbl_qty, rounded_price, rounded_qty):
    try:
        lbl_price.config(text=str(rounded_price), foreground="#2e7d32")  # green
    except Exception:
        pass
    try:
        lbl_qty.config(text=str(rounded_qty), foreground="#ef6c00")      # orange
    except Exception:
        pass


def set_window_title(root, version: str = "MontrixBot 1.2-pre2 — Preview"):
    """Set window title for preview builds; safe no-op on failure."""
    try:
        root.title(version)
    except Exception:
        # In preview hooks we never want to crash the UI just because of title
        pass


def open_runtime_folder():
    import os, sys, subprocess
    path = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'runtime'))
    if sys.platform.startswith("win"):
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
