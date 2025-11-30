import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runtime.state_manager import StateManager
from core.position_manager import Position, PositionManager
from runtime import tpsl_loop
from runtime.price_cache import set_price
import time, json

os.makedirs(os.path.join(ROOT, "runtime"), exist_ok=True)
settings_path = os.path.join(ROOT, "runtime", "settings.json")
try:
    with open(settings_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
except Exception:
    cfg = {}
cfg.setdefault("tpsl_autoloop", {"enabled": True, "interval_sec": 2, "min_move_pct": 0.35})
with open(settings_path, "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)

state = StateManager()
pm = PositionManager(state)

symbol = "ADAUSDT"
entry = 0.400000
qty = 10

p = Position(symbol=symbol, qty=qty, entry_price=entry, tp=None, sl=None)
pm.upsert_position(p)

def _get_price(sym):
    from runtime.price_cache import get_cached_price
    return get_cached_price(sym)

set_price(symbol, 0.400000)
runner = tpsl_loop.start(cfg, _get_price)

print(">>> TPSL smoke test started. Watch logs for trailing updates.")
seq = [0.404, 0.408, 0.415, 0.420, 0.418, 0.412, 0.410]
for pr in seq:
    set_price(symbol, pr)
    print(f"Price -> {pr}")
    time.sleep(cfg["tpsl_autoloop"].get("interval_sec", 2))
print(">>> Stopping loop...")
tpsl_loop.stop()
print(">>> Done. Check runtime/state.json and logs.")
