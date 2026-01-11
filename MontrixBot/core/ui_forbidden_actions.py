# MontrixBot
# UI-only hardening: single source of truth for UI-forbidden actions (read-only mode).
# NOTE: This module is intentionally dependency-free and safe to import from both core and UI.

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class UIActionSpec:
    code: str
    title: str
    kind: str = "WRITE"  # informational (UI-only)


# Canonical registry (SSOT) for actions that are considered "write" from UI perspective.
# These codes must match UIAPI._guard_write(action=...) callers.
UI_FORBIDDEN_ACTIONS: Dict[str, UIActionSpec] = {
    # Trading / position controls
    "close_position": UIActionSpec("close_position", "Закрытие позиции из UI"),
    "panic": UIActionSpec("panic", "Паник-действие из UI"),
    "activate_panic_kill": UIActionSpec("activate_panic_kill", "Panic Kill из UI"),

    # REAL diag (must remain blocked in read-only)
    "real_buy_market": UIActionSpec("real_buy_market", "REAL BUY MARKET (diag)"),
    "real_sell_market": UIActionSpec("real_sell_market", "REAL SELL MARKET (diag)"),

    # Runtime / persistence / state mutation
    "persist_equity_point": UIActionSpec("persist_equity_point", "Запись equity point (runtime)"),
    "persist_trade_record": UIActionSpec("persist_trade_record", "Запись trade record (runtime)"),
    "persist_sim_state": UIActionSpec("persist_sim_state", "Персист SIM-состояния"),
    "maybe_persist_runtime_state": UIActionSpec("maybe_persist_runtime_state", "Throttled runtime persist"),
    "reset_sim_state": UIActionSpec("reset_sim_state", "Сброс SIM-состояния"),
    "update_tpsl_settings_from_ui": UIActionSpec("update_tpsl_settings_from_ui", "Изменение TPSL настроек из UI"),
}


def normalize_ui_action(action: str) -> str:
    """
    Normalize action code for logging/events (never raises).
    We keep original codes stable, only trimming whitespace.
    """
    try:
        s = str(action or "").strip()
        return s if s else "UNKNOWN_ACTION"
    except Exception:
        return "UNKNOWN_ACTION"


def describe_ui_action(action: str) -> str:
    """
    Human label for UI action code. Returns code itself if unknown.
    """
    code = normalize_ui_action(action)
    spec = UI_FORBIDDEN_ACTIONS.get(code)
    if spec is None:
        return code
    return spec.title
