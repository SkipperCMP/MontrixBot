from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Sequence


def create_topbar(app: Any, symbols: Sequence[str]) -> None:
    """Builds topbar + path buttons row for given App.

    Это тонкий мост к существующим ui.widgets.controls_bar.build_* функциям.
    Логика и конкретные виджеты остаются там, здесь только вызовы.
    """
    try:
        # Запуск как пакет: python -m ui.main_app
        from ..widgets.controls_bar import build_topbar_ui, build_paths_ui  # type: ignore
    except Exception:
        # Запуск как скрипт: python python ui/main_app.py
        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from ui.widgets.controls_bar import build_topbar_ui, build_paths_ui  # type: ignore

    build_topbar_ui(app, symbols)
    build_paths_ui(app)

