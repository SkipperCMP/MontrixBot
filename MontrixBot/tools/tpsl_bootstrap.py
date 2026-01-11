
def get_price(symbol: str):
    # Connect to runtime.price_cache by default
    try:
        from runtime.price_cache import get_cached_price
        return get_cached_price(symbol)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("get_price failed")
        return None

def start_tpsl_if_enabled():
    """
    CLI bootstrap for TPSL autoloop.

    No policy decisions here.
    Delegates to core.
    """
    try:
        from core.tpsl_settings_api import request_tpsl_autostart
        return request_tpsl_autostart(get_price)
    except Exception:
        return None

if __name__ == "__main__":
    runner = start_tpsl_if_enabled()
    print("Bot started. TPSL:", "RUNNING" if runner else "DISABLED")
