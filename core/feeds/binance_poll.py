# core/feeds/binance_poll.py
# Лёгкий REST-пуллер без внешних зависимостей. Опрашивает 24hr ticker раз в N секунд.
import json, threading, time, urllib.request, urllib.error

API_URL = "https://api.binance.com/api/v3/ticker/24hr?symbols={symbols}"

class BinancePollThread(threading.Thread):
    def __init__(self, symbols, on_quote, interval_sec=2.0):
        super().__init__(daemon=True)
        self.symbols = [s.upper() for s in symbols]
        self.on_quote = on_quote
        self.interval = interval_sec
        self._stop = threading.Event()

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
                            if s: self.on_quote(s, c, P)
                        except Exception:
                            continue
            except Exception:
                # тихо пропускаем сбои сети и пробуем снова
                pass
            time.sleep(self.interval)

    def stop(self):
        self._stop.set()
