# ui/layout/statusbar.py
from tkinter import ttk
from tkinter import Frame
from typing import NamedTuple

class StatusbarView(NamedTuple):
    frame: Frame
    # labels / indicators

def create_statusbar(parent: Frame):
    frame = ttk.Frame(parent)
    frame.grid(row=4, column=0, columnspan=2, sticky="nsew")
    return StatusbarView(frame=frame)
