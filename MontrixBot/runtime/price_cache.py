# Price cache with ring buffer for basic volatility estimation
from collections import deque

_price = {}
_buf = {}

def set_price(symbol: str, price: float, buf_size: int = 100):
    k = str(symbol).upper()
    _price[k] = float(price)
    dq = _buf.get(k)
    if dq is None:
        dq = deque(maxlen=buf_size)
        _buf[k] = dq
    dq.append(float(price))

def get_cached_price(symbol: str):
    return _price.get(str(symbol).upper())

def get_window_extrema(symbol: str, window: int):
    k = str(symbol).upper()
    dq = _buf.get(k)
    if not dq:
        return (None, None)
    if window <= 0 or window >= len(dq):
        data = list(dq)
    else:
        data = list(dq)[-window:]
    if not data:
        return (None, None)
    return (min(data), max(data))
