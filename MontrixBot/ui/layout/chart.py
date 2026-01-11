# ui/layout/chart.py
from tkinter import ttk
from tkinter import Frame
from typing import NamedTuple

from ui.state.ui_state import UIState

class ChartView(NamedTuple):
    frame: Frame
    # сюда позже добавятся canvas, toolbar и т.п.

def create_chart(parent: Frame, ui_state: UIState):
    frame = ttk.Frame(parent)
    frame.grid(row=2, column=0, sticky="nsew")
    return ChartView(frame=frame)
