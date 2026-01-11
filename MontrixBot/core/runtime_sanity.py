from __future__ import annotations

from typing import Any, Dict, List
import logging

from . import runtime_state


logger = logging.getLogger("montrix.runtime_sanity")


def run_runtime_sanity_check() -> Dict[str, Any]:
    """
    Лёгкая проверка целостности runtime-состояния.

    Ничего не изменяет и не выбрасывает исключения наружу:
    - читает runtime через runtime_state.load_runtime_state();
    - выполняет несколько дешёвых проверок структуры;
    - логирует предупреждения/ошибки и возвращает структурированный отчёт.
    """
    try:
        state = runtime_state.load_runtime_state()
    except Exception:
        logger.exception("runtime_sanity: failed to load runtime state")
        return {
            "ok": False,
            "error": "failed_to_load_runtime_state",
            "issues": ["failed_to_load_runtime_state"],
            "warnings": [],
            "summary": {},
        }

    issues: List[str] = []
    warnings: List[str] = []

    positions = state.get("positions", {})
    meta = state.get("meta", {})
    sim = state.get("sim", {})

    # Базовая проверка типов верхнего уровня
    if not isinstance(positions, dict):
        issues.append(f"positions is {type(positions).__name__}, expected dict")
    if not isinstance(meta, dict):
        issues.append(f"meta is {type(meta).__name__}, expected dict")
    if not isinstance(sim, dict):
        issues.append(f"sim is {type(sim).__name__}, expected dict")

    # Проверяем структуру позиций
    if isinstance(positions, dict):
        bad_keys: List[str] = []
        for key, value in positions.items():
            if not isinstance(value, dict):
                bad_keys.append(str(key))
        if bad_keys:
            issues.append(
                "Non-dict position entries at keys: " + ", ".join(sorted(bad_keys))
            )

    # Согласованность meta.open_positions и фактического числа позиций (если поле есть)
    open_cnt = None
    if isinstance(meta, dict) and "open_positions" in meta:
        if isinstance(meta["open_positions"], int):
            open_cnt = meta["open_positions"]
            if isinstance(positions, dict) and open_cnt != len(positions):
                warnings.append(
                    f"meta.open_positions={open_cnt} but positions_count={len(positions)}"
                )

    ok = not issues

    if not ok:
        logger.warning("runtime_sanity: detected issues: %s", "; ".join(issues))
    elif warnings:
        logger.info("runtime_sanity: warnings: %s", "; ".join(warnings))
    else:
        logger.debug("runtime_sanity: state looks sane")

    summary = {
        "positions_count": len(positions) if isinstance(positions, dict) else None,
        "meta_keys": sorted(meta.keys()) if isinstance(meta, dict) else [],
        "sim_keys": sorted(sim.keys()) if isinstance(sim, dict) else [],
    }

    return {
        "ok": ok,
        "issues": issues,
        "warnings": warnings,
        "summary": summary,
    }
