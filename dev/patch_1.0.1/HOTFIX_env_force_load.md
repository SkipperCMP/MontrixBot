
# Hotfix — force-load .env for any entrypoint
- Added tools/env_force_load.py with ensure_env_loaded()
- Patched core/orders_real.py to load .env on import
- Patched scripts/real_sandbox_buy.py to load .env before using keys
