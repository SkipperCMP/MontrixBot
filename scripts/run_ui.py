"""UI runner (canonical).

This script must start the canonical UI entrypoint (ui.main_app).
Legacy ui.app_step9 is canon-disabled and must not be used.
"""

from ui.main_app import launch

# STEP 1.4.7: persist Recovery Contract boot info before UI starts (core-owned)
try:
    from core.runtime_state import ensure_safe_boot_contract_persisted
    ensure_safe_boot_contract_persisted()
except Exception:
    pass

# Start canonical UI
launch()
