import json, os

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
    settings = _load_settings()
    tp = settings.get("tpsl_autoloop", {})
    if not tp.get("enabled", True):
        return None
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
