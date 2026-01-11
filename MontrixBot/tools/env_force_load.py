
# tools/env_force_load.py — ensure .env is loaded for any entrypoint
def ensure_env_loaded():
    try:
        from dotenv import load_dotenv, find_dotenv
        load_dotenv(find_dotenv(), override=False)
    except Exception:
        pass
