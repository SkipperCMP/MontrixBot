
"""
tpsl_loop.py — лёгкий демон-трафикатор (SCaffold)
Пока работает в режиме "наблюдателя":
 - читает runtime/tpsl_config.json
 - если enabled=false или dry=true — только логирует шаги
Интеграция в UI/ядро будет в 1.1.
"""
import time, json, os, sys
from datetime import datetime

CFG = "runtime/tpsl_config.json"
# POLICY-01: файловая health-телеметрия запрещена
LOG = None

def load_cfg():
    try:
        with open(CFG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def jlog(obj):
    # POLICY-01: файловый health_log.jsonl запрещён
    # Логирование TPSL отключено до 1.5.x
    return

def main():
    jlog({"tpsl":"start", "note":"scaffold"})
    while True:
        cfg = load_cfg()
        if not cfg.get("enabled") or cfg.get("dry", True):
            jlog({"tpsl":"idle","enabled":cfg.get("enabled",False),"dry":cfg.get("dry",True)})
        else:
            # Здесь будет реальная логика в 1.1
            jlog({"tpsl":"tick","note":"active-mode placeholder"})
        time.sleep(max(0.5, cfg.get("poll_ms",800)/1000.0))

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        jlog({"tpsl":"stop"})
