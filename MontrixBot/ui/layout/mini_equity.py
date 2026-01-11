# ui/layout/mini_equity.py
from tkinter import ttk
from tkinter import Frame
from typing import NamedTuple

from ui.state.ui_state import UIState

class MiniEquityView(NamedTuple):
    frame: Frame
    # progressbar / label

def create_mini_equity(parent: Frame, ui_state: UIState):
    frame = ttk.Frame(parent)
    frame.grid(row=1, column=0, columnspan=2, sticky="nsew")
    return MiniEquityView(frame=frame)
