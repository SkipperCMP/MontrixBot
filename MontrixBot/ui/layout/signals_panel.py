# ui/layout/signals_panel.py
from tkinter import ttk
from tkinter import Frame
from typing import NamedTuple

class SignalsPanelView(NamedTuple):
    frame: Frame
    # tree/list и т.п.

def create_signals_panel(parent: Frame):
    frame = ttk.Frame(parent)
    # пока можно не размещать, подключим в 1.3.5 аккуратнее
    return SignalsPanelView(frame=frame)
