from __future__ import annotations

"""
core/runtime_state.py — STEP 1.3.3 Runtime-Consistency (pre3)

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
import time

from runtime.state_manager import StateManager
from runtime.sim_state_tools import load_sim_state, save_sim_state, clear_sim_state

logger = logging.getLogger(__name__)

_LOG_THROTTLE = {}

def _log_throttled(key: str, msg: str, *, interval_s: float = 60.0):
    try:
        now = time.time()
        last = _LOG_THROTTLE.get(key, 0.0)
        if now - last < interval_s:
            return
        _LOG_THROTTLE[key] = now
        logger.exception(msg)
    except Exception:
        return

# Путь к основному state.json (позиции, метаданные и т.п.)
STATE_PATH = os.path.join("runtime", "state.json")

# STEP 1.4.7: Recovery Contract defaults
DEFAULT_STRATEGY_STATE = "PAUSED"   # ON | PAUSED
DEFAULT_TRADING_GATE = "ALLOW"      # ALLOW | DENY   (gate is about REAL trading)

# Глобальный менеджер основного state.json
_state_manager = StateManager(STATE_PATH)


def _ensure_base_structure(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Гарантирует минимально валидную и типобезопасную структуру runtime-состояния.

    - Всегда возвращает dict;
    - Обязательно содержит ключи "positions", "meta", "sim";
    - Значения по этим ключам всегда dict (при некорректных типах — мягкий reset).
    """
    if not isinstance(data, dict):
        logger.error("runtime_state: got non-dict state, resetting to empty dict")
        data = {}

    # positions: гарантируем dict
    positions = data.get("positions")
    if positions is None:
        data["positions"] = {}
    elif not isinstance(positions, dict):
        logger.warning(
            "runtime_state: 'positions' is not a dict (%s), resetting to {}",
            type(positions).__name__,
        )
        data["positions"] = {}

    # meta: гарантируем dict
    meta = data.get("meta")
    if meta is None:
        data["meta"] = {}
    elif not isinstance(meta, dict):
        logger.warning(
            "runtime_state: 'meta' is not a dict (%s), resetting to {}",
            type(meta).__name__,
        )
        data["meta"] = {}

    # STEP 1.4.7: Recovery Contract fields (backward compatible)
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    try:
        meta.setdefault("strategy_state", DEFAULT_STRATEGY_STATE)
        meta.setdefault("trading_gate", DEFAULT_TRADING_GATE)
        meta.setdefault("safe_boot_reason", "")
        meta.setdefault("safe_boot_ts", 0.0)
        meta.setdefault("last_boot", {})
        if not isinstance(meta.get("last_boot"), dict):
            meta["last_boot"] = {}
        data["meta"] = meta
    except Exception:
        _log_throttled(
            "runtime_state.ensure_base_structure",
            "runtime_state: failed to ensure meta recovery fields",
            interval_s=300.0,
        )

    # sim: гарантируем dict, но не создаём его из мусора
    sim = data.get("sim")
    if sim is None:
        data["sim"] = {}
    elif not isinstance(sim, dict):
        logger.warning(
            "runtime_state: 'sim' is not a dict (%s), resetting to {}",
            type(sim).__name__,
        )
        data["sim"] = {}

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
    # IMPORTANT: read must be side-effect free (UI read-only + test stability).
    try:
        base = _state_manager.read()
        if not isinstance(base, dict):
            base = {}
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
        _log_throttled(
            "runtime_state.reset_sim",
            "runtime_state: failed to clear sim_state.json",
            interval_s=120.0,
        )

def _detect_boot_conditions() -> Dict[str, Any]:
    """
    STEP 1.4.7: Detect boot-time safety conditions.
    CORE-owned. Best-effort. Never raises.
    """
    panic_active = False
    panic_reason = ""
    safe_lock_on = False

    # PANIC
    try:
        from core import panic_tools  # type: ignore
        panic_active = bool(getattr(panic_tools, "is_panic_active")())
        if panic_active:
            # best-effort: read reason from settings.json if available
            try:
                cfg = getattr(panic_tools, "_load_settings")()
                p = (cfg.get("panic") or {}) if isinstance(cfg, dict) else {}
                panic_reason = str(p.get("reason") or "PANIC")
            except Exception:
                panic_reason = "PANIC"
    except Exception:
        panic_active = False
        panic_reason = ""

    # HARD_LOCK (SAFE_MODE file)
    try:
        from tools.safe_lock import is_safe_on  # type: ignore
        safe_lock_on = bool(is_safe_on())
    except Exception:
        safe_lock_on = False

    # Compose reason
    if panic_active:
        reason = f"PANIC(settings):{panic_reason}" if panic_reason else "PANIC(settings)"
    elif safe_lock_on:
        reason = "HARD_LOCK(file)"
    else:
        reason = "CLEAN"

    return {
        "panic_active": panic_active,
        "panic_reason": panic_reason,
        "safe_lock_on": safe_lock_on,
        "reason": reason,
    }

def ensure_safe_boot_contract_persisted() -> Dict[str, Any]:
    """
    STEP 1.4.7: Persist Recovery Contract boot info into runtime/state.json.

    - Does NOT grant UI authority.
    - Does NOT auto-resume strategy.
    - Sets trading_gate=DENY when PANIC or HARD_LOCK is present.
    """
    boot = _detect_boot_conditions()
    now = time.time()

    def _patch(current: Dict[str, Any]) -> Dict[str, Any]:
        data = _ensure_base_structure(dict(current) if isinstance(current, dict) else {})
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        meta.setdefault("strategy_state", DEFAULT_STRATEGY_STATE)

        # Gate REAL trading under unsafe boot conditions
        if boot.get("panic_active") or boot.get("safe_lock_on"):
            meta["trading_gate"] = "DENY"
        else:
            meta.setdefault("trading_gate", DEFAULT_TRADING_GATE)

        meta["safe_boot_reason"] = str(boot.get("reason") or "")
        meta["safe_boot_ts"] = float(now)

        lb = meta.get("last_boot")
        if not isinstance(lb, dict):
            lb = {}
        lb.update(
            {
                "ts": float(now),
                "reason": str(boot.get("reason") or ""),
                "panic_active": bool(boot.get("panic_active")),
                "safe_lock_on": bool(boot.get("safe_lock_on")),
            }
        )
        meta["last_boot"] = lb
        data["meta"] = meta
        return data

    try:
        _state_manager.update(_patch)
    except Exception:
        logger.exception("runtime_state: ensure_safe_boot_contract_persisted failed")

    # Return current merged state (for logging/UI read only)
    try:
        return load_runtime_state()
    except Exception:
        _log_throttled(
            "runtime_state.safe_boot.return",
            "runtime_state: failed to reload runtime state after safe boot persist",
            interval_s=120.0,
        )
        return {}

def compute_trading_gate(state: dict) -> str:
    """
    Единственный источник допуска REAL.
    Возвращает: ALLOW | DENY
    """
    meta = (state or {}).get("meta") or {}

    if meta.get("strategy_state") == "PAUSED":
        return "DENY"

    # SAFE / PANIC обрабатываются на уровне orders_real
    return "ALLOW"
