
# ui/theme_dark.py
import tkinter as tk
from tkinter import ttk

def apply_neutral_dark(style: ttk.Style):
    # Base palette
    bg   = "#0f1216"  # base
    fg   = "#E6EAF2"  # text
    card = "#171B21"  # surfaces
    acc1 = "#2F6FED"  # primary (blue)
    acc2 = "#7A8AA6"  # muted
    warn = "#FFC857"  # warning
    err  = "#FF6B6B"  # danger
    ok   = "#2ecc71"  # success

    style.theme_use("clam")
    style.configure(".", background=bg, foreground=fg, fieldbackground=card)
    style.configure("TFrame", background=bg)
    style.configure("TLabelframe", background=bg, bordercolor=card, relief="groove")
    style.configure("TLabelframe.Label", background=bg, foreground=fg)
    style.configure("TLabel", background=bg, foreground=fg)
    style.configure("TButton", background=card, foreground=fg, relief="flat", padding=6)
    style.map("TButton",
              background=[("active", "#1f2530")],
              relief=[("pressed", "sunken")])
    style.configure("TCombobox", fieldbackground=card, background=card, foreground=fg, arrowcolor=fg)
    style.map("TCombobox", fieldbackground=[("readonly", card)])
    style.configure("TEntry", fieldbackground=card, insertcolor=fg, foreground=fg)
    style.configure("Horizontal.TSeparator", background=card)

    # Badges
    style.configure("Badge.TLabel", padding=(8,3), borderwidth=0)
    style.configure("SIM.TLabel", background="#0D3B66", foreground=fg)            # blue-dark
    style.configure("DRY.TLabel", background=warn, foreground="#111")
    style.configure("ARMED.TLabel", background=err, foreground="#111")
    style.configure("OK.TLabel", background=ok, foreground="#111")
    style.configure("MUTED.TLabel", background=acc2, foreground="#111")

    return {
        "bg": bg, "fg": fg, "card": card, "acc1": acc1, "acc2": acc2,
        "warn": warn, "err": err, "ok": ok
    }
