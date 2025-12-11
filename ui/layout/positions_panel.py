from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


def create_positions_panel(app: Any) -> None:
    """Builds 'active position' panel for given App.

    Это тонкий мост к ui.widgets.positions_panel.build_activepos_ui.
    Все реальные виджеты и логика остаются там.
    """
    try:
        # Запуск как пакет: python -m ui.app_step9
        from ..widgets.positions_panel import build_activepos_ui  # type: ignore
    except Exception:
        # Запуск как скрипт: python ui/app_step9.py
        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from ui.widgets.positions_panel import build_activepos_ui  # type: ignore

    build_activepos_ui(app)
