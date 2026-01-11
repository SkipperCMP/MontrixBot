from __future__ import annotations

"""
core/runtime_persistence.py — STEP1.3.3 Runtime Persistence (pre2)

Промежуточный слой между UI-снапшотом и core/runtime_state.py.

Задача:
- принять "толстый" UI-снапшот (positions, portfolio, mode/dry_run, advisor);
- аккуратно обновить runtime-state (positions + meta),
  НЕ трогая sim-часть, которая живёт в sim_state.json.
"""

from typing import Any, Dict
import logging
from . import runtime_state

logger = logging.getLogger("montrix.runtime_persistence")


def _merge_meta_from_snapshot(old_meta: Dict[str, Any], snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge existing runtime meta with meta information coming from a UI snapshot.

    Rules:
    - Start from old_meta (if it is a dict), then overlay "meta" block from snapshot.
    - Additionally, pull top-level convenience fields:
        - mode: "SIM" / "REAL"
        - dry_run: bool
    - If snapshot carries a "portfolio" dict, propagate basic equity/PnL fields
      into a nested "portfolio" block inside meta.
    """
    merged: Dict[str, Any] = {}
    if isinstance(old_meta, dict):
        merged.update(old_meta)

    # 1) Direct "meta" block from snapshot (highest priority)
    new_meta = snapshot.get("meta")
    if isinstance(new_meta, dict):
        merged.update(new_meta)

    # 2) Mode / dry_run from top-level snapshot
    mode = snapshot.get("mode")
    if mode in ("SIM", "REAL"):
        merged["mode"] = mode

    dry_run = snapshot.get("dry_run")
    if isinstance(dry_run, bool):
        merged["dry_run"] = dry_run

    # 3) Portfolio/equity info (optional)
    portfolio = snapshot.get("portfolio")
    if isinstance(portfolio, dict):
        portfolio_meta = merged.get("portfolio")
        if not isinstance(portfolio_meta, dict):
            portfolio_meta = {}
        # копируем только базовые ключи, если они есть
        for key in ("equity", "equity_usdt", "unrealized_pnl", "realized_pnl"):
            if key in portfolio:
                portfolio_meta[key] = portfolio[key]
        merged["portfolio"] = portfolio_meta

    return merged

def persist_from_ui_snapshot(snapshot: Dict[str, Any]) -> None:
    """
    STEP1.3.3 Runtime Persistence (pre1)
    Update persistent runtime state from a UI snapshot.

    Responsibilities:
    - Validate snapshot structure (must be a dict).
    - Update `positions` and `meta` branches in runtime-state.
    - Explicitly DO NOT touch the `sim` branch here.
    """
    logger.debug("persist_from_ui_snapshot: incoming snapshot type=%s", type(snapshot).__name__)

    # Basic type safety: we only accept dict snapshots
    if not isinstance(snapshot, dict):
        logger.warning("persist_from_ui_snapshot: snapshot is not a dict, skipping")
        return

    # Load current runtime-state
    try:
        runtime = runtime_state.load_runtime_state()
    except Exception:
        logger.exception(
            "persist_from_ui_snapshot: failed to load runtime-state, starting from empty"
        )
        runtime = {}

    if not isinstance(runtime, dict):
        # extremely defensive: if load_runtime_state returned something unexpected
        logger.warning(
            "persist_from_ui_snapshot: runtime-state is not a dict (%s), resetting to {}",
            type(runtime).__name__,
        )
        runtime = {}

    # ------------------------------------------------------------------
    # 1) Positions: snapshot["positions"] wins if it's a proper dict
    # ------------------------------------------------------------------
    snapshot_positions = snapshot.get("positions")
    if isinstance(snapshot_positions, dict):
        runtime["positions"] = snapshot_positions
    else:
        logger.debug(
            "persist_from_ui_snapshot: no valid 'positions' block in snapshot "
            "(got %s), keeping existing positions",
            type(snapshot_positions).__name__,
        )

    # ------------------------------------------------------------------
    # 2) Meta: merge old runtime["meta"] with meta + flags from snapshot
    # ------------------------------------------------------------------
    old_meta = runtime.get("meta")
    if not isinstance(old_meta, dict):
        old_meta = {}

    merged_meta = _merge_meta_from_snapshot(old_meta, snapshot)
    runtime["meta"] = merged_meta

    # ------------------------------------------------------------------
    # 3) SIM branch: must NOT be touched here
    # ------------------------------------------------------------------
    sim_branch = runtime.get("sim")
    if sim_branch is not None and not isinstance(sim_branch, dict):
        # Если sim-ветка повреждена, починим, но не заполняем данными из snapshot
        logger.warning(
            "persist_from_ui_snapshot: runtime.sim is not a dict (%s), resetting to {}",
            type(sim_branch).__name__,
        )
        runtime["sim"] = {}

    # ------------------------------------------------------------------
    # 4) Persist updated runtime-state
    # ------------------------------------------------------------------
    try:
        runtime_state.save_runtime_state(runtime)
        logger.debug("persist_from_ui_snapshot: runtime-state persisted successfully")
    except Exception:
        logger.exception("persist_from_ui_snapshot: failed to save runtime-state")
