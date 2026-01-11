
"""
tools/binance_time_sync.py — Time sync helper for Binance Spot (1.0.1+)

References (official):
- /api/v3/time — Server time: https://developers.binance.com/docs/binance-spot-api-docs/rest-api#test-connectivity
- Signed endpoints & timestamp/recvWindow: https://developers.binance.com/docs/binance-spot-api-docs/rest-api#endpoint-security-type
- Error codes (-1021 TIME_IN_FORCE): https://github.com/binance/binance-spot-api-docs/blob/master/errors.md
- Binance US auth types: https://docs.binance.us/#authentication-types
"""
from __future__ import annotations
import time, json, os, math, threading
from dataclasses import dataclass
from typing import Optional
import requests

RUNTIME_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "runtime"))
OFFSET_FILE = os.path.join(RUNTIME_DIR, "time_offset.json")

DEFAULT_RECV_WINDOW_MS = 5000   # conservative default
MAX_ALLOWED_DRIFT_MS = 1000     # aim to keep |offset| < 1s

@dataclass
class TimeStatus:
    local_ts: int
    server_ts: int
    offset_ms: int
    recv_window_ms: int

_session = requests.Session()
_lock = threading.Lock()

def _save_offset(offset_ms: int, recv_window_ms: int = DEFAULT_RECV_WINDOW_MS):
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    with open(OFFSET_FILE, "w", encoding="utf-8") as f:
        json.dump({"offset_ms": int(offset_ms), "recv_window_ms": int(recv_window_ms), "ts": int(time.time()*1000)}, f)

def _load_offset() -> tuple[int, int]:
    try:
        with open(OFFSET_FILE, "r", encoding="utf-8") as f:
            j = json.load(f)
            return int(j.get("offset_ms", 0)), int(j.get("recv_window_ms", DEFAULT_RECV_WINDOW_MS))
    except Exception:
        return 0, DEFAULT_RECV_WINDOW_MS

def server_time(endpoint: str = "https://api.binance.com/api/v3/time") -> int:
    """Return server time in ms. (Spot API: /api/v3/time)"""
    r = _session.get(endpoint, timeout=5)
    r.raise_for_status()
    j = r.json()
    return int(j["serverTime"])

def sync_time(endpoint: str = "https://api.binance.com/api/v3/time") -> TimeStatus:
    """Sync local clock with Binance server time and persist offset in runtime/time_offset.json"""
    with _lock:
        t_local_before = int(time.time()*1000)
        t_server = server_time(endpoint)
        t_local_after = int(time.time()*1000)
        # Approximate RTT midpoint correction
        midpoint = (t_local_before + t_local_after)//2
        offset = int(t_server - midpoint)  # positive => server ahead of local
        _save_offset(offset, DEFAULT_RECV_WINDOW_MS)
        return TimeStatus(local_ts=midpoint, server_ts=t_server, offset_ms=offset, recv_window_ms=DEFAULT_RECV_WINDOW_MS)

def current_offset() -> TimeStatus:
    off, rw = _load_offset()
    return TimeStatus(local_ts=int(time.time()*1000), server_ts=0, offset_ms=off, recv_window_ms=rw)

def signed_params_with_ts(params: dict | None = None) -> dict:
    """
    Prepare standard signed params with corrected timestamp and recvWindow.
    Call this BEFORE HMAC signing.
    """
    params = dict(params or {})
    off, rw = _load_offset()
    params["timestamp"] = int(time.time()*1000) + int(off)
    params["recvWindow"] = int(rw)
    return params

def is_drift_ok(threshold_ms: int = MAX_ALLOWED_DRIFT_MS) -> bool:
    """Return True if saved offset is within the threshold."""
    off, _ = _load_offset()
    return abs(off) <= int(threshold_ms)
