from __future__ import annotations

import threading
import time
from typing import Dict, Any, Optional

_lock = threading.Lock()
_last_ts: Dict[str, float] = {}

def beat(component: str, ts: Optional[float] = None) -> None:
    """Mark component heartbeat timestamp (best-effort, thread-safe)."""
    try:
        name = str(component or "").strip().lower()
        if not name:
            return
        now = float(ts if ts is not None else time.time())
        with _lock:
            _last_ts[name] = now
    except Exception:
        return

def snapshot(now: Optional[float] = None) -> Dict[str, Any]:
    """Return heartbeat timestamps + ages (seconds) for known components."""
    try:
        t = float(now if now is not None else time.time())
        with _lock:
            ts_map = dict(_last_ts)
        ages = {k: (t - float(v)) for k, v in ts_map.items()}
        return {"ts": ts_map, "age_s": ages, "now": t}
    except Exception:
        return {"ts": {}, "age_s": {}, "now": time.time()}
