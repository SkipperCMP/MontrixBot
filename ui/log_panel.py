
def log_tpsl(logger, message: str):
    """
    Безопасный шорткат для логов TPSL.
    Используйте log_tpsl(logger, "...") вместо прямого print в UI.
    """
    try:
        logger(message)
    except Exception:
        print(message)
