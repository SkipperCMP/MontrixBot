
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
LOG = "runtime/health_log.jsonl"

def load_cfg():
    try:
        with open(CFG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def jlog(obj):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        obj["ts"] = datetime.utcnow().isoformat(timespec="seconds")+"Z"
        f.write(json.dumps(obj, ensure_ascii=False)+"\n")

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
