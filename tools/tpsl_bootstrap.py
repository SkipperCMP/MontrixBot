import json
import os

from core.runtime_state import ensure_safe_boot_contract_persisted


def _load_settings():
    p = "runtime/settings.json"
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_price(symbol: str):
    # Connect to runtime.price_cache by default
    try:
        from runtime.price_cache import get_cached_price
        return get_cached_price(symbol)
    except Exception:
        return None


def start_tpsl_if_enabled():
    """
    STEP 1.4.7 — Runtime Recovery & Safe Boot (TPSL autoloop bootstrap)

    - Фиксирует Recovery Contract при старте
    - Никогда не запускает TPSL autoloop при PANIC или HARD_LOCK
    - Не бросает исключений наружу
    """

    # 1) Persist Safe Boot contract (best-effort, core-owned)
    try:
        ensure_safe_boot_contract_persisted()
    except Exception:
        pass

    # 2) Запрещаем TPSL autoloop при небезопасном старте
    try:
        from core.panic_tools import is_panic_active
        from tools.safe_lock import is_safe_on

        if bool(is_panic_active()) or bool(is_safe_on()):
            return None
    except Exception:
        # если не смогли проверить — ведём себя консервативно
        return None

    # 3) Проверяем настройку автолоопа
    settings = _load_settings()
    tp = settings.get("tpsl_autoloop", {})
    if not tp.get("enabled", True):
        return None

    # 4) Старт TPSL autoloop
    try:
        from runtime import tpsl_loop
        runner = tpsl_loop.start(settings, get_price)
        return runner
    except Exception as e:
        print(f"TPSL start failed: {e}")
        return None


if __name__ == "__main__":
    runner = start_tpsl_if_enabled()
    print("Bot started. TPSL:", "RUNNING" if runner else "DISABLED")
