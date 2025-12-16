try:
    from ui.app_step9 import launch
except Exception as e:
    raise  # не делаем fallback на более старый UI

# STEP 1.4.7: persist Recovery Contract boot info before UI starts (core-owned)
try:
    from core.runtime_state import ensure_safe_boot_contract_persisted
    ensure_safe_boot_contract_persisted()
except Exception:
    pass

# First run without internet uses synthetic feed
launch(symbols=["ADAUSDT", "HBARUSDT", "BONKUSDT"], use_public_feed=False)
