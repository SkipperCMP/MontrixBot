"""
LAYOUT BRIDGE MODULE.

This file intentionally contains NO UI logic.
It wires layout -> widgets.positions_panel.build_activepos_ui.

Single source of UI implementation:
- ui/widgets/positions_panel.py

This module exists to:
- keep layout separation
- support different app entrypoints
"""
from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


def create_positions_panel(app: Any, parent: Any = None) -> None:
    """
    Builds 'Active Position' panel for given App.

    CONTRACT:
    - app MUST provide method: app._set_active_text(str)
    - this function performs ONE-TIME UI construction
    - no runtime updates are handled here

    DESIGN:
    - thin layout bridge only
    - all widget logic lives in ui.widgets.positions_panel
    """
    try:
        # Запуск как пакет: python -m ui.main_app
        from ..widgets.positions_panel import build_activepos_ui  # type: ignore
    except Exception:
        # Запуск как скрипт: python ui/main_app.py
        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from ui.widgets.positions_panel import build_activepos_ui  # type: ignore

    build_activepos_ui(app, parent=parent)
