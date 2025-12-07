
# core/binance_real.py
from __future__ import annotations
import os, time, hmac, hashlib, urllib.parse, urllib.request, json, threading
from typing import Optional, Dict, Any

DEFAULT_BASE = os.environ.get("BINANCE_BASE", "https://api.binance.com")
API_KEY = os.environ.get("BINANCE_API_KEY", "").strip()
API_SECRET = os.environ.get("BINANCE_SECRET", "").strip().encode("utf-8")
RECV_WINDOW = int(os.environ.get("BINANCE_RECV_WINDOW", "5000"))

class BinanceREST:
    def __init__(self, base: str|None=None, api_key: str|None=None, api_secret: str|None=None, recv_window: int|None=None):
        self.base = (base or DEFAULT_BASE).rstrip("/")
        self.api_key = (api_key or API_KEY).strip()
        self.api_secret = (api_secret or API_SECRET).strip().encode("utf-8") if isinstance(api_secret or API_SECRET, str) else (api_secret or API_SECRET)
        self.recv_window = int(recv_window or RECV_WINDOW)

    # --- low level
    def _sign(self, qs: str) -> str:
        return hmac.new(self.api_secret, qs.encode("utf-8"), hashlib.sha256).hexdigest()

    def _headers(self) -> Dict[str,str]:
        return {"X-MBX-APIKEY": self.api_key, "User-Agent": "MontrixBot/1.2-pre2"}

    def _req(self, method: str, path: str, params: Dict[str, Any]|None=None, signed: bool=False, timeout=15) -> dict:
        url = self.base + path
        params = params or {}
        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["recvWindow"] = self.recv_window
            qs = urllib.parse.urlencode(params, doseq=True)
            params["signature"] = self._sign(qs)
        data = None
        if method in ("GET","DELETE"):
            if params:
                url += "?" + urllib.parse.urlencode(params, doseq=True)
        else:
            data = urllib.parse.urlencode(params, doseq=True).encode("utf-8")
        req = urllib.request.Request(url, data=data, method=method, headers=self._headers())
        with urllib.request.urlopen(req, timeout=timeout) as r:
            txt = r.read().decode("utf-8")
            if not txt: return {}
            return json.loads(txt)

    # --- public helpers (minimal subset)
    def create_market_order(self, symbol: str, side: str, quantity: float) -> dict:
        return self._req("POST", "/api/v3/order", {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": "MARKET",
            "quantity": quantity
        }, signed=True)

    # user data stream (optional for 1.0 baseline; best-effort only)
    def get_listen_key(self) -> Optional[str]:
        try:
            data = self._req("POST", "/api/v3/userDataStream")
            return data.get("listenKey")
        except Exception:
            return None

    def keepalive_listen_key(self, listen_key: str) -> bool:
        try:
            self._req("PUT", "/api/v3/userDataStream", {"listenKey": listen_key})
            return True
        except Exception:
            return False

    def close_listen_key(self, listen_key: str) -> bool:
        try:
            self._req("DELETE", "/api/v3/userDataStream", {"listenKey": listen_key})
            return True
        except Exception:
            return False
