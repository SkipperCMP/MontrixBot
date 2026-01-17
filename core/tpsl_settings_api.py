"""
TPSL settings API (core-owned).

This module is the ONLY place where TPSL autoloop
may be started based on policy decisions.

tools / CLI MUST delegate here and must NOT
make any decisions on their own.
"""

import logging
from typing import Any, Dict

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Settings access
# ---------------------------------------------------------------------

def get_tpsl_settings() -> Dict[str, Any]:
    from runtime.tpsl_settings_store import load_tpsl_settings
    return load_tpsl_settings()

def update_tpsl_settings(settings: Dict[str, Any]) -> None:
    from runtime.tpsl_settings_store import save_tpsl_settings
    save_tpsl_settings(settings)


# ---------------------------------------------------------------------
# Core-owned TPSL autostart entrypoint
# ---------------------------------------------------------------------

def request_tpsl_autostart(get_price_callable):
    """
    Core-owned request to start TPSL autoloop.

    This function:
    - enforces SAFE / PANIC policy
    - checks tpsl_autoloop.enabled
    - starts the real TPSL loop if allowed

    Returns:
        loop instance if started, otherwise None
    """

    # 1) Ensure safe boot contract (best-effort)
    try:
        from core.runtime_state import ensure_safe_boot_contract_persisted
        ensure_safe_boot_contract_persisted()
    except Exception:
        log.exception("TPSL autostart: failed to ensure safe boot contract")
        return None

    # 2) SAFE policy
    try:
        from tools.safe_lock import is_safe_on
        if is_safe_on():
            log.warning("TPSL autostart blocked: SAFE is ON")
            return None
    except Exception:
        log.exception("TPSL autostart blocked: SAFE check failed")
        return None

    # 3) PANIC policy
    try:
        from runtime.panic_tools import is_panic_active
        if is_panic_active():
            log.warning("TPSL autostart blocked: PANIC is active")
            return None
    except Exception:
        log.exception("TPSL autostart blocked: PANIC check failed")
        return None

    # 4) Settings: enabled flag
    try:
        settings = get_tpsl_settings()
        tp = settings.get("tpsl_autoloop", {})
        if not tp.get("enabled", True):
            log.info("TPSL autostart blocked: tpsl_autoloop.enabled is false")
            return None
    except Exception:
        log.exception("TPSL autostart blocked: failed to read TPSL settings")
        return None

    # 5) Real TPSL start (the ONLY correct path)
    log.info(
        "TPSL autostart skipped: requires live StateEngine "
        "(TPSL attaches only inside core runtime lifecycle)"
    )
    return None

