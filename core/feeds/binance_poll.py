# core/feeds/binance_poll.py
# Лёгкий REST-пуллер без внешних зависимостей. Опрашивает 24hr ticker раз в N секунд.
import json, threading, time, urllib.request, urllib.error, logging

log = logging.getLogger(__name__)
_last_warn_ts: float = 0.0
_err_count: int = 0

API_URL = "https://api.binance.com/api/v3/ticker/24hr?symbols={symbols}"

class BinancePollThread(threading.Thread):
    def __init__(self, symbols, on_quote, interval_sec=2.0):
        super().__init__(daemon=True)
        self.symbols = [s.upper() for s in symbols]
        self.on_quote = on_quote
        self.interval = interval_sec
        self._stop = threading.Event()

    def _maybe_push_stats(self, symbol: str, high_24h: float, low_24h: float, vol_24h: float, pct_24h: float) -> None:
        """
        Best-effort: если on_quote — bound-method, и его владелец имеет update_market_stats(),
        то прокидываем market stats в UIAPI (или другой объект-агрегатор).
        """
        try:
            cb = self.on_quote
            owner = getattr(cb, "__self__", None)
            if owner is None:
                return
            fn = getattr(owner, "update_market_stats", None)
            if not callable(fn):
                return
            fn(
                str(symbol).upper(),
                {
                    "high_24h": float(high_24h),
                    "low_24h": float(low_24h),
                    "volume_24h": float(vol_24h),
                    "pct_24h": float(pct_24h),
                },
            )
        except Exception:
            return

    def run(self):
        while not self._stop.is_set():
            try:
                url = API_URL.format(symbols=json.dumps(self.symbols))
                with urllib.request.urlopen(url, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list):
                    for d in data:
                        try:
                            s = d.get("symbol")
                            c = float(d.get("lastPrice") or 0.0)
                            P = float(d.get("priceChangePercent") or 0.0)

                            h = float(d.get("highPrice") or 0.0)
                            l = float(d.get("lowPrice") or 0.0)
                            v = float(d.get("volume") or 0.0)

                            if s:
                                self.on_quote(s, c, P)
                                self._maybe_push_stats(s, h, l, v, P)
                        except Exception:
                            continue
            except Exception:
                # пропускаем сбои сети и пробуем снова, но не молча
                global _last_warn_ts, _err_count
                _err_count += 1
                now = time.time()
                if (now - float(_last_warn_ts or 0.0)) >= 60.0:
                    _last_warn_ts = now
                    log.warning(
                        f"BinancePollThread: network/parse error (count={_err_count}), continuing",
                        exc_info=True,
                    )
            time.sleep(self.interval)

    def stop(self):
        self._stop.set()
