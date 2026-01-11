# core/feeds/binance_book_ws.py
import json
import threading
import time
import ssl
from typing import Iterable, Callable, Optional

import logging
from core import heartbeats as hb

log = logging.getLogger(__name__)
_LOG_THROTTLE = {}

def _log_throttled(key: str, level: str, msg: str, *, interval_s: float = 60.0, exc_info: bool = False):
    try:
        now = time.time()
        last = _LOG_THROTTLE.get(key, 0.0)
        if now - last < interval_s:
            return
        _LOG_THROTTLE[key] = now
        fn = getattr(log, level, log.warning)
        fn(msg, exc_info=exc_info)
    except Exception:
        return

try:
    import websocket  # type: ignore
except Exception:
    websocket = None

# Spot WS docs: combined streams wrapper: {"stream":"...","data":{...}} and bookTicker payload has fields s,b,a,B,A
# https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams
WS_BASE = "wss://data-stream.binance.vision"

class BinanceBookTickerThread(threading.Thread):
    """
    Streams best bid/ask via <symbol>@bookTicker for a list of symbols (combined stream).
    Callback signature:
        on_book(symbol: str, bid: float, ask: float, bid_qty: float, ask_qty: float) -> None
    """
    def __init__(
        self,
        symbols: Iterable[str],
        on_book: Callable[[str, float, float, float, float], None],
        *,
        trace: bool = False,
        insecure_ssl: bool = False,
        base_url: str = WS_BASE,
    ):
        super().__init__(daemon=True)
        self.symbols = [str(s).upper() for s in symbols]
        self.on_book = on_book
        self._stop = threading.Event()
        self._ws: Optional[object] = None
        self._trace = trace
        self._sslopt = {"cert_reqs": ssl.CERT_NONE} if insecure_ssl else None
        self._base_url = str(base_url).rstrip("/")

        streams = "/".join([f"{s.lower()}@bookTicker" for s in self.symbols])
        self._url = f"{self._base_url}/stream?streams={streams}"

    def run(self):
        if websocket is None:
            print("[BinanceBookWS] Не найден модуль websocket-client. Установите: python -m pip install websocket-client")
            return

        if self._trace:
            try:
                websocket.enableTrace(True)
            except Exception:
                _log_throttled(
                    "binance_book_ws.trace",
                    "debug",
                    "BinanceBookWS: enableTrace failed",
                    interval_s=300.0,
                    exc_info=True,
                )

        while not self._stop.is_set():
            try:
                self._ws = websocket.WebSocketApp(
                    self._url,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                    on_pong=self._on_pong,
                )
                self._ws.on_open = self._on_open
                # More tolerant keepalive settings to avoid false timeouts on flaky networks/proxies.
                # Binance may drop idle connections; websocket-client ping helps keep NATs alive.
                self._ws.run_forever(
                    ping_interval=30,   # MUST be > ping_timeout
                    ping_timeout=10,
                    skip_utf8_validation=True,
                    sslopt=self._sslopt or {},
                )
            except Exception as e:
                print("[BinanceBookWS] reconnect after error:", repr(e))
            time.sleep(2.0)

    def stop(self):
        self._stop.set()
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            _log_throttled(
                "binance_book_ws.stop",
                "debug",
                "BinanceBookWS: ws.close() failed during stop",
                interval_s=120.0,
                exc_info=True,
            )

    # --- WS callbacks ---
    def _on_open(self, _ws):
        print("[BinanceBookWS] connected")

    def _on_pong(self, _ws, _data):
        # keepalive heartbeat
        try:
            hb.beat("ws_book_pong")
        except Exception:
            return

    def _on_close(self, _ws, *args):
        _log_throttled("binance_book_ws.close", "warning", "[BinanceBookWS] closed", interval_s=15.0)

    def _on_error(self, _ws, err):
        _log_throttled(
            "binance_book_ws.err",
            "warning",
            f"[BinanceBookWS] error: {repr(err)}",
            interval_s=15.0,
        )

    def _on_message(self, _ws, message):
        try:
            msg = json.loads(message)
            hb.beat("ws_book")
        except Exception:
            _log_throttled(
                "binance_book_ws.json",
                "debug",
                "BinanceBookWS: failed to decode JSON message",
                interval_s=60.0,
                exc_info=True,
            )
            return

        # combined stream wrapper: {"stream":"...","data":{...}}
        data = msg.get("data") if isinstance(msg, dict) else None
        if not isinstance(data, dict):
            return

        try:
            s = str(data.get("s") or "").upper()
            if not s:
                return

            bid = float(data.get("b") or 0.0)
            ask = float(data.get("a") or 0.0)
            bid_qty = float(data.get("B") or 0.0)
            ask_qty = float(data.get("A") or 0.0)

            # basic sanity
            if bid <= 0 and ask <= 0:
                return

            self.on_book(s, bid, ask, bid_qty, ask_qty)
        except Exception:
            _log_throttled(
                "binance_book_ws.item",
                "debug",
                "BinanceBookWS: bad bookTicker item skipped",
                interval_s=60.0,
                exc_info=True,
            )
            return
