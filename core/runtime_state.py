from __future__ import annotations

"""
core/runtime_state.py — STEP 1.3.2 Runtime-Save (pre1)

Единая точка доступа к runtime/state.json и runtime/sim_state.json
для CORE и ui_api.

Задачи:
- дать безопасные функции load_runtime_state() / save_runtime_state();
- НЕ дублировать логику StateManager и sim_state_tools;
- не знать ничего про UI.
"""

from typing import Any, Dict, Optional
import logging
import os

from runtime.state_manager import StateManager
from runtime.sim_state_tools import load_sim_state, save_sim_state, clear_sim_state

logger = logging.getLogger(__name__)

# Путь к основному state.json (позиции, метаданные и т.п.)
STATE_PATH = os.path.join("runtime", "state.json")

# Глобальный менеджер основного state.json
_state_manager = StateManager(STATE_PATH)


def _ensure_base_structure(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Гарантирует минимально валидную структуру runtime-состояния.

    Если чего-то нет — аккуратно добавляем по умолчанию, но не ломаем
    существующие поля.
    """
    if not isinstance(data, dict):
        logger.error("runtime_state: got non-dict state, resetting to empty dict")
        data = {}

    # Минимальные обязательные секции
    data.setdefault("positions", {})
    data.setdefault("meta", {})
    data.setdefault("sim", {})

    return data


def load_runtime_state() -> Dict[str, Any]:
    """
    Безопасное чтение объединённого runtime-состояния.

    Возвращает dict вида:
    {
        "positions": {...},
        "meta": {...},
        "sim": {...}  # может быть пустым, если sim_state.json ещё не создавался
        ... другие поля ...
    }

    Никогда не выбрасывает исключения наружу — максимум логирует ошибки
    и возвращает минимально валидную структуру.
    """
    # 1) базовое состояние из state.json через StateManager
    try:
        base: Dict[str, Any] = {}

        def _capture(current: Dict[str, Any]) -> Dict[str, Any]:
            nonlocal base
            if isinstance(current, dict):
                base = dict(current)
            else:
                base = {}
            # ничего не меняем в файле
            return current

        _state_manager.update(_capture)
    except Exception:
        logger.exception("runtime_state: failed to read base state via StateManager")
        base = {}

    # 2) SIM-состояние из sim_state.json
    sim: Optional[Dict[str, Any]] = None
    try:
        sim = load_sim_state()
    except Exception:
        logger.exception("runtime_state: failed to load sim_state.json")

    state = _ensure_base_structure(base)

    if sim is not None and isinstance(sim, dict):
        state["sim"] = sim

    return state


def save_runtime_state(new_state: Dict[str, Any]) -> None:
    """
    Безопасное сохранение runtime-состояния.

    Ожидает структуру вида:
    {
        "positions": {...},
        "meta": {...},      # опционально
        "sim": {...},       # опционально, будет сохранён в sim_state.json
        ... другие поля ...
    }

    - Часть, относящаяся к основному state.json, пробрасывается через StateManager;
    - Поле "sim", если есть, сохраняется в sim_state.json через save_sim_state().
    """
    if not isinstance(new_state, dict):
        logger.error("runtime_state: save_runtime_state got non-dict payload, ignoring")
        return

    base_for_disk = dict(new_state)
    sim_part: Optional[Dict[str, Any]] = None

    if "sim" in base_for_disk:
        raw_sim = base_for_disk.pop("sim")
        if isinstance(raw_sim, dict):
            sim_part = raw_sim
        else:
            logger.warning(
                "runtime_state: 'sim' field is not a dict, skipping save_sim_state()"
            )

    base_for_disk = _ensure_base_structure(base_for_disk)

    # 1) Сохранение основной части через StateManager
    try:
        def _overwrite(_: Dict[str, Any]) -> Dict[str, Any]:
            return dict(base_for_disk)

        _state_manager.update(_overwrite)
    except Exception:
        logger.exception("runtime_state: failed to save base state via StateManager")

    # 2) Сохранение SIM-части (если есть)
    if sim_part is not None:
        try:
            save_sim_state(sim_part)
        except Exception:
            logger.exception("runtime_state: failed to save sim_state.json")

def reset_sim_state() -> None:
    """
    Полный сброс SIM-состояния на уровне runtime.

    Внешний мир (UI, скрипты) должен пользоваться только этим методом,
    а не трогать runtime/sim_state.json напрямую.
    """
    try:
        clear_sim_state()
    except Exception:
        # Логируем, но не выбрасываем наружу: сброс SIM не критичен.
        logger.exception("runtime_state: failed to clear sim_state.json")
