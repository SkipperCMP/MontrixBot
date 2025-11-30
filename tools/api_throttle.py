
# tools/api_throttle.py — simple per-endpoint rate limiter + backoff (1.0.1+)
from __future__ import annotations
import time, threading, random
from typing import Callable

class RateLimiter:
    def __init__(self, min_interval_ms: int = 120):
        self.min_interval = max(0, int(min_interval_ms)) / 1000.0
        self._lock = threading.Lock()
        self._last = 0.0

    def acquire(self):
        with self._lock:
            now = time.monotonic()
            dt = now - self._last
            if dt < self.min_interval:
                time.sleep(self.min_interval - dt)
            self._last = time.monotonic()

_global_rl = RateLimiter(120)
_endpoint_rl = {}

def limiter_for(key: str, min_interval_ms: int = 120) -> RateLimiter:
    rl = _endpoint_rl.get(key)
    if rl is None:
        rl = RateLimiter(min_interval_ms)
        _endpoint_rl[key] = rl
    return rl

def backoff_sleep(attempt: int, base: float = 0.3, cap: float = 5.0):
    t = min(cap, base * (2 ** attempt))
    time.sleep(t * (0.5 + random.random()*0.5))

def throttled_call(fn: Callable, *args, key: str = "global", attempts: int = 5, **kwargs):
    rl = _global_rl if key == "global" else limiter_for(key)
    err = None
    for i in range(attempts):
        rl.acquire()
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            err = e
            backoff_sleep(i)
            continue
    raise err if err else RuntimeError("throttled_call failed without exception")
