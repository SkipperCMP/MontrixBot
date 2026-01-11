from __future__ import annotations

"""
runtime/tpsl_settings_store.py — единое хранилище TPSL-настроек UI.

Задача:
- безопасно читать/писать runtime/settings.json (или другой TPSL-файл),
  не давая UI работать с файловой системой напрямую.
"""

from pathlib import Path
from typing import Any, Dict
import json
import logging

logger = logging.getLogger(__name__)

SETTINGS_PATH = Path("runtime/settings.json")


def _default_settings() -> Dict[str, Any]:
    """
    Базовые TPSL-настройки по умолчанию.

    ⚠️ Сюда нужно перенести те default-значения, которые сейчас
    создаются внутри ui/tpsl_controls.py (там, где формируется dict
    при отсутствии файла или ошибке чтения).
    """
    return {
        # примеры, замени на реальные поля из ui/tpsl_controls.py:
        # "tpsl_enabled": True,
        # "sl_percent": 5.0,
        # "tp_percent": 10.0,
    }


def load_tpsl_settings() -> Dict[str, Any]:
    """
    Безопасное чтение TPSL-настроек.

    Никогда не кидает исключения наружу:
    - при любой ошибке вернёт структуру по умолчанию.
    """
    try:
        if SETTINGS_PATH.exists():
            raw = SETTINGS_PATH.read_text(encoding="utf-8")
            if raw.strip():
                data = json.loads(raw)
                if isinstance(data, dict):
                    # дополняем недостающие поля default-значениями
                    base = _default_settings()
                    base.update(data)
                    return base
    except Exception:
        logger.exception("tpsl_settings_store: failed to read settings.json")

    # если файла нет или он битый — возвращаем defaults
    return _default_settings()


def save_tpsl_settings(settings: Dict[str, Any]) -> None:
    """
    Безопасная запись TPSL-настроек.

    При ошибке — только лог, без исключений наружу.
    """
    try:
        data = dict(_default_settings())
        if isinstance(settings, dict):
            data.update(settings)

        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        logger.exception("tpsl_settings_store: failed to write settings.json")
