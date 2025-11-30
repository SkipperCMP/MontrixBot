from __future__ import annotations
"""
core/state_engine.py — STEP1.7 Hooks + StateEngine (part 1)

Минимальный, но рабочий движок состояния цены (тикерный StateEngine),
который:

* хранит последние тики по символам;
* отдаёт snapshot() для UI / тестов;
* при каждом апдейте:
    - пишет тик в ipc_ticks (tools/ipc_ticks.append_tick), чтобы UI мог рисовать график;
    - нотифицирует TPSLManager через on_price, если он подключён.

Этот модуль специально сделан лёгким и без прямых зависимостей от Binance:
он может использоваться и в оффлайн-тестах, и в реальном стриме.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from core.tradebook import TradeBook

# ------ optional hooks: ipc_ticks ------

try:  # best-effort: UI-график через локальный JSONL
    from tools.ipc_ticks import append_tick as _append_tick  # type: ignore
except Exception:  # pragma: no cover
    def _append_tick(*args, **kwargs) -> None:  # type: ignore[override]
        return None


# ------ optional hooks: TPSL ------

try:
    from core.tpsl import TPSLManager  # type: ignore
except Exception:  # pragma: no cover
    TPSLManager = None  # type: ignore[misc]


@dataclass
class Ticker:
    """Единичный тик по символу.

    last — последняя цена сделки
    bid  — лучшая цена bid (если известна)
    ask  — лучшая цена ask (если известна)
    ts   — timestamp в секундах (float)
    """

    last: float
    bid: float
    ask: float
    ts: float = field(default_factory=time.time)


class StateEngine:
    """Простой движок состояния тиков.

    В текущей версии отвечает только за:
    - хранение последних цен по каждому символу;
    - публикацию тиков в ipc_ticks;
    - нотификацию TPSLManager.on_price().

    Логика портфеля / equity / PnL вынесена в другие модули (autosim, TPSL и др.).
    """

    def __init__(self, enable_tpsl: bool = True) -> None:
        self.version: int = 0
        self.ticks: Dict[str, Ticker] = {}
        self._lock = threading.RLock()

        # журнал сделок для UI (используется UIAPI/Executor)
        self.tradebook: TradeBook = TradeBook()

        # TPSL-хук (может быть None, если TPSL не используется)
        self.tpsl: Optional[TPSLManager] = None  # type: ignore[assignment]
        self._enable_tpsl: bool = bool(enable_tpsl)

    # ----------------- TPSL hook -----------------

    def attach_tpsl(self, manager: TPSLManager) -> None:  # type: ignore[valid-type]
        """Подключить TPSLManager к StateEngine.

        Если enable_tpsl=False, on_price вызываться не будет,
        но ссылка хранится (на будущее).
        """
        self.tpsl = manager

    # ----------------- public API -----------------

    def snapshot(self) -> Dict[str, Any]:
        """Вернуть лёгкий снапшот состояния.

        Формат:
        {
            "version": int,
            "ticks": {...},
            "deals_rows": [...],  # строки для журнала сделок (TradeBook)
        }
        """
        with self._lock:
            return {
                "version": self.version,
                "ticks": {
                    sym: {"last": t.last, "bid": t.bid, "ask": t.ask, "ts": t.ts}
                    for sym, t in self.ticks.items()
                },
                # best-effort: журнал сделок для UI
                "deals_rows": self.tradebook.export_rows(),
            }

    def get_ticker_last(self, symbol: str) -> Optional[float]:
        """Вернуть последнюю цену по символу (или None)."""
        if not symbol:
            return None
        sym = symbol.upper()
        with self._lock:
            t = self.ticks.get(sym)
            if not t:
                return None
            return float(t.last)

    def upsert_ticker(
        self,
        symbol: str,
        last: float,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
        ts: Optional[float] = None,
    ) -> int:
        """Обновить тик по символу и вернуть новый version.

        * symbol — строка символа (например, "ADAUSDT");
        * last   — последняя цена сделки;
        * bid/ask — опциональные лучшая покупка/продажа;
        * ts     — timestamp; если не задан, берётся time.time().
        """
        if not symbol:
            return self.version

        sym = symbol.upper()
        now_ts = ts or time.time()

        # нормализуем цены (если bid/ask не заданы — берём last)
        try:
            last_f = float(last)
        except Exception:
            return self.version

        try:
            bid_f = float(bid) if bid is not None else last_f
        except Exception:
            bid_f = last_f

        try:
            ask_f = float(ask) if ask is not None else last_f
        except Exception:
            ask_f = last_f

        # --- запись под локом ---
        with self._lock:
            t = Ticker(last=last_f, bid=bid_f, ask=ask_f, ts=now_ts)
            self.ticks[sym] = t

            # best-effort: пишем тик в ipc_ticks для UI
            try:
                _append_tick(
                    {
                        "symbol": sym,
                        "price": t.last,
                        "bid": t.bid,
                        "ask": t.ask,
                        "ts": t.ts,
                    }
                )
            except Exception:
                # график — вспомогательный, не должен ломать поток
                pass

            self.version += 1
            new_version = self.version

        # --- вне локов: нотификация TPSL ---
        if self._enable_tpsl and self.tpsl is not None:
            try:
                # TPSLManager ожидает on_price(symbol, price, ts)
                self.tpsl.on_price(sym, float(last_f), now_ts)  # type: ignore[call-arg]
            except Exception:
                # TP/SL не должен ронять основной поток тиков
                pass

        return new_version
