from __future__ import annotations

import json
import os
import time
from typing import Any, Dict

from tools.safe_lock import enable_safe

SETTINGS_PATH = os.path.join("runtime", "settings.json")
PANIC_FLAG = os.path.join("runtime", "panic.flag")

def _try_delegate_panic_to_core(reason: str) -> bool:
    """
    Try to delegate PANIC activation to core-owned policy.

    Returns True if delegation succeeded, False otherwise.
    """
    try:
        # Preferred: core-owned entrypoint (to be implemented/confirmed)
        from core.safe_mode import request_panic  # type: ignore
        request_panic(reason=reason)
        return True
    except Exception:
        return False

def _load_settings() -> Dict[str, Any]:
    """Безопасное чтение runtime/settings.json.

    В контексте PANIC нам важнее не упасть, чем идеально отловить все ошибки.
    """
    if not os.path.exists(SETTINGS_PATH):
        return {}
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_settings(cfg: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def activate_panic(reason: str = "panic") -> None:
    """Глобальный PANIC-KILL.

    Делает три вещи:
    - включает SAFE_MODE (через tools.safe_lock.enable_safe);
    - помечает panic-режим в runtime/settings.json;
    - создаёт файл runtime/panic.flag для других процессов.
    Плюс по возможности выключает TPSL-автолооп в этом процессе.
    """

    # 0) First: delegate to core-owned PANIC policy, if available.
    # This makes runtime a thin trigger (no policy decisions here).
    if _try_delegate_panic_to_core(reason):
        return

    # 1) включаем SAFE_MODE для REAL
    enable_safe()

    # 2) помечаем panic в settings + отключаем автолооп
    cfg = _load_settings()
    panic_cfg = cfg.setdefault("panic", {})
    panic_cfg["active"] = True
    panic_cfg["reason"] = reason
    panic_cfg["since"] = time.time()

    tp_cfg = cfg.setdefault("tpsl_autoloop", {})
    tp_cfg["enabled"] = False

    try:
        _save_settings(cfg)
    except Exception:
        # В PANIC допускаем best-effort запись
        pass

    # 3) ставим файл-флаг
    try:
        os.makedirs(os.path.dirname(PANIC_FLAG), exist_ok=True)
        with open(PANIC_FLAG, "w", encoding="utf-8") as f:
            f.write(reason or "panic")
    except Exception:
        pass

    # 4) если TPSL-луп запущен в этом же процессе — попробуем его остановить
    try:
        from core import tpsl_loop  # type: ignore
        if hasattr(tpsl_loop, "stop"):
            tpsl_loop.stop()  # type: ignore[arg-type]
    except Exception:
        # Если TPSL крутится в другом процессе — просто игнорируем
        pass


def clear_panic() -> None:
    """Сбрасывает panic-флаг в settings и удаляет runtime/panic.flag.

    SAFE_MODE намеренно не трогаем — это отдельное осознанное действие.
    """
    cfg = _load_settings()
    panic_cfg = cfg.setdefault("panic", {})
    panic_cfg["active"] = False
    panic_cfg["reason"] = ""
    panic_cfg["since"] = None
    try:
        _save_settings(cfg)
    except Exception:
        pass

    try:
        os.remove(PANIC_FLAG)
    except FileNotFoundError:
        pass
    except Exception:
        pass


def is_panic_active() -> bool:
    """Лёгкая проверка: активен ли panic-режим."""
    if os.path.exists(PANIC_FLAG):
        return True
    cfg = _load_settings()
    panic_cfg = cfg.get("panic") or {}
    return bool(panic_cfg.get("active"))
