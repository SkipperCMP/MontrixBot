# core/feeds/binance_ws.py (PATCH12)
import json
import threading
import time
import ssl
from typing import Iterable, Callable

try:
    import websocket  # type: ignore
except Exception:
    websocket = None

STREAM_URL = "wss://stream.binance.com:9443/ws/!miniTicker@arr"

class BinanceMiniTickerThread(threading.Thread):
    def __init__(self, symbols: Iterable[str], on_quote: Callable[[str, float, float], None],
                 trace: bool=False, insecure_ssl: bool=False):
        super().__init__(daemon=True)
        self.symbols = {s.upper() for s in symbols}
        self.on_quote = on_quote
        self._stop = threading.Event()
        self._ws = None
        self._trace = trace
        self._sslopt = {"cert_reqs": ssl.CERT_NONE} if insecure_ssl else None

    def run(self):
        if websocket is None:
            print("[BinanceWS] Не найден модуль websocket-client. Установите: python -m pip install websocket-client")
            return
        if self._trace:
            try:
                websocket.enableTrace(True)
            except Exception:
                pass
        while not self._stop.is_set():
            try:
                self._ws = websocket.WebSocketApp(
                    STREAM_URL,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self._ws.on_open = self._on_open
                self._ws.run_forever(ping_interval=15, ping_timeout=10, sslopt=self._sslopt or {})
            except Exception as e:
                print("[BinanceWS] reconnect after error:", repr(e))
            time.sleep(2.0)

    def stop(self):
        self._stop.set()
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            pass

    # --- WS callbacks ---
    def _on_open(self, _ws):
        print("[BinanceWS] connected")

    def _on_close(self, _ws, *args):
        print("[BinanceWS] closed")

    def _on_error(self, _ws, err):
        print("[BinanceWS] error:", repr(err))

    def _on_message(self, _ws, message):
        # !miniTicker@arr отдаёт массив объектов mini-ticker.
        # В НИХ НЕТ поля 'P' (percent), есть 'o' (open) и 'c' (last).
        # Поэтому процент считаем сами, а если вдруг есть 'P' (на некоторых источниках) — используем его.
        try:
            arr = json.loads(message)
        except Exception:
            return
        if not isinstance(arr, list):
            return
        for it in arr:
            try:
                s = it.get("s")
                if s not in self.symbols:
                    continue
                # last & open
                c = float(it.get("c") or 0.0)
                o = float(it.get("o") or 0.0)
                # иногда встречается 'P' — используем при наличии, иначе считаем сами
                if it.get("P") not in (None, "", 0, "0", "0.0"):
                    pct = float(it.get("P"))
                else:
                    pct = ((c - o) / o * 100.0) if o else 0.0
                self.on_quote(s, c, pct)
            except Exception:
                continue
