from __future__ import annotations

"""
core/runtime_persistence.py — STEP1.3.3 Runtime Persistence (pre10)

Промежуточный слой между UI-снапшотом и core/runtime_state.py.

Задача:
- принять "толстый" UI-снапшот (positions, portfolio, mode/dry_run, advisor);
- аккуратно обновить runtime-state (positions + meta),
  НЕ трогая sim-часть, которая живёт в sim_state.json.
"""

from typing import Any, Dict

import logging

from core.runtime_state import load_runtime_state, save_runtime_state

logger = logging.getLogger(__name__)


def persist_from_ui_snapshot(snapshot: Dict[str, Any]) -> None:
    """
    Обновить runtime_state на основе UI-снапшота.

    Ожидаемый формат snapshot (совместим с UIAPI._build_state_payload):

    {
        "positions": {...},          # словарь позиций TPSL
        "portfolio": {...},          # equity, pnl_day_pct, ...
        "mode": "SIM"|"REAL",        # UI-режим
        "dry_run": bool,             # флаг Dry-Run для UI
        "advisor": {...},            # последний сигнал/рекомендация (опционально)
        ...
    }

    Логика:
    - читаем текущий runtime_state через load_runtime_state();
    - обновляем поля:
        * positions <- snapshot["positions"] (если dict),
        * meta.mode, meta.dry_run, meta.portfolio, meta.advisor;
    - sim-подраздел НЕ трогаем (оставляем как есть);
    - сохраняем всё обратно через save_runtime_state().
    """
    if not isinstance(snapshot, dict):
        return

    try:
        current = load_runtime_state()
    except Exception:
        logger.exception("runtime_persistence: failed to load current runtime_state")
        current = {}

    if not isinstance(current, dict):
        current = {}

    # --- positions ---
    positions = snapshot.get("positions") or {}
    if not isinstance(positions, dict):
        positions = {}

    # --- meta / portfolio / flags ---
    meta = current.get("meta") or {}
    if not isinstance(meta, dict):
        meta = {}

    mode = snapshot.get("mode")
    if mode is not None:
        meta["mode"] = mode

    dry_run = snapshot.get("dry_run")
    if dry_run is not None:
        meta["dry_run"] = dry_run

    portfolio = snapshot.get("portfolio") or {}
    if isinstance(portfolio, dict):
        meta["portfolio"] = portfolio

    advisor = snapshot.get("advisor") or {}
    if isinstance(advisor, dict):
        meta["advisor"] = advisor

    # Собираем новое состояние, не трогая sim / другие поля.
    new_state: Dict[str, Any] = dict(current)
    new_state["positions"] = positions
    if meta:
        new_state["meta"] = meta

    try:
        save_runtime_state(new_state)
    except Exception:
        logger.exception("runtime_persistence: failed to save runtime_state")
