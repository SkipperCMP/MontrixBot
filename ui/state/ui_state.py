# ui/state/ui_state.py
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class UIState:
    selected_symbol: str = "BTCUSDT"
    selected_theme: str = "dark"
    is_sim_mode: bool = True
    # сюда позже можно добавлять флаги compact-mode, фильтры и т.д.
