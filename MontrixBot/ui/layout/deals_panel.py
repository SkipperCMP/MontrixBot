# ui/layout/deals_panel.py
from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


def create_deals_panel(app: Any, StatusBar: Any, parent: Any = None) -> None:
    """Создаёт лог-панель + StatusBar для данного app.

    Это тонкий мост к ui.widgets.log_panel.build_log_ui.
    Вся реальная разметка и логика остаются в widgets.
    """
    try:
        # Запуск как пакет: python -m ui.main_app
        from ..widgets.log_panel import build_log_ui  # type: ignore
    except Exception:
        # Запуск как скрипт: python ui/main_app.py
        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from ui.widgets.log_panel import build_log_ui  # type: ignore

    build_log_ui(app, StatusBar, parent=parent)
