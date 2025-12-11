from __future__ import annotations

import json
import os
import tempfile
import time
from typing import Any, Dict, Optional

SIM_STATE_PATH = os.path.join("runtime", "sim_state.json")


def load_sim_state() -> Optional[Dict[str, Any]]:
    """Безопасное чтение runtime/sim_state.json.

    Используется только для SIM-режима, чтобы аккуратно подхватить последний снимок.
    Если файл отсутствует, пустой или битый — возвращает None.
    """
    if not os.path.exists(SIM_STATE_PATH):
        return None

    try:
        with open(SIM_STATE_PATH, "r", encoding="utf-8") as f:
            txt = f.read()
    except Exception:
        return None

    if not txt.strip():
        return None

    try:
        data = json.loads(txt)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    # обогащаем минимальной мета-информацией
    meta = data.setdefault("meta", {})
    meta.setdefault("version", "sim_state_v1")
    meta["loaded_at"] = time.time()
    return data


def save_sim_state(snapshot: Dict[str, Any]) -> None:
    """Атомарная запись runtime/sim_state.json.

    Никаких исключений наружу не выбрасывает — в SIM-режиме потеря снапшота не
    должна ломать UI.
    """
    if not isinstance(snapshot, dict):
        return

    data: Dict[str, Any] = dict(snapshot)
    meta = data.setdefault("meta", {})
    meta.setdefault("version", "sim_state_v1")
    meta["saved_at"] = time.time()

    directory = os.path.dirname(SIM_STATE_PATH) or "."
    os.makedirs(directory, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(prefix="sim_state_", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, SIM_STATE_PATH)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

def clear_sim_state() -> None:
    """
    Полный сброс файла runtime/sim_state.json (best-effort).

    Используется, когда нужно принудительно забыть SIM-снимок,
    например по запросу от UI ('Reset SIM').
    """
    try:
        if os.path.exists(SIM_STATE_PATH):
            os.remove(SIM_STATE_PATH)
    except Exception:
        # Любые ошибки при удалении файла игнорируем:
        # сброс SIM не должен ломать основной процесс.
        pass
