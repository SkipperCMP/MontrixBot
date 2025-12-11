from __future__ import annotations

"""
core/tpsl_settings_api.py — адаптер TPSL-настроек для UIAPI.

UI ничего не знает про runtime-файлы:
UI  →  core.ui_api  →  core.tpsl_settings_api  →  runtime.tpsl_settings_store
"""

from typing import Dict, Any

from runtime.tpsl_settings_store import load_tpsl_settings, save_tpsl_settings


def get_tpsl_settings() -> Dict[str, Any]:
    """
    Прочитать TPSL-настройки для UI (через runtime.tpsl_settings_store).
    """
    return load_tpsl_settings()


def update_tpsl_settings(new_settings: Dict[str, Any]) -> None:
    """
    Обновить TPSL-настройки (сохранить на диск через runtime.tpsl_settings_store).
    """
    save_tpsl_settings(new_settings)
