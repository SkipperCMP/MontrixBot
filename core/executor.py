# core/executor.py — 1.2-pre2 STEP1.2.14
# OrderExecutor + Preview + JSONL journal for trades (SIM)

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Dict
import json
import os
import time


JOURNAL_PATH_DEFAULT = "runtime/trades.jsonl"


@dataclass
class Preview:
    ok: bool
    reason: str = ""
    info: str = ""
    rounded_price: float | None = None
    rounded_qty: float | None = None


def _ensure_not_real(mode: str) -> None:
    # В этой ветке реализована только SIM/DRY-логика.
    assert mode != "REAL", "Dry-run path must never execute in REAL mode"


def _append_jsonl(path: str, event: Dict[str, Any]) -> None:
    """Append single JSON object to a .jsonl file.

    Используется и OrderExecutor, и (косвенно) другие модули для trades.jsonl.
    Ошибки глушатся, чтобы журнал не ломал основную логику.
    """
    try:
        if not path:
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        # журнал — вспомогательный, не должен ронять поток
        pass


@dataclass
class OrderResult:
    """Упрощённый результат ордера для TPSL/логирования.

    Хранит только то, что реально используется:
    - price / qty нужны TPSLManager.close
    - raw содержит ответ core.orders.place_order (status, orderId, mode)
    """
    price: float
    qty: float
    raw: Dict[str, Any]


class OrderExecutor:
    def __init__(
        self,
        mode: str = "SIM",
        state: Optional[object] = None,
        journal_path: str = JOURNAL_PATH_DEFAULT,
    ):
        self.mode = mode
        self.state = state
        # trades.jsonl (совместимо с TPSLManager по умолчанию)
        self.journal_path = journal_path

    def set_mode(self, mode: str) -> None:
        """
        STEP 1.4.7: UI may request mode switch, but REAL is gated by SAFE/PANIC.
        Core-owned safety: if unsafe -> force SIM.
        """
        m = (mode or "SIM").upper()
        if m not in ("SIM", "REAL"):
            m = "SIM"

        if m == "REAL":
            try:
                from core.panic_tools import is_panic_active
                from tools.safe_lock import is_safe_on
                if bool(is_panic_active()) or bool(is_safe_on()):
                    self.mode = "SIM"
                    return
            except Exception:
                self.mode = "SIM"
                return

        self.mode = m

    # -------- helpers --------
    def _last_price(self, symbol: str) -> float:
        try:
            if hasattr(self.state, "get_ticker_last"):
                return float(self.state.get_ticker_last(symbol))
            if hasattr(self.state, "tickers"):
                t = getattr(self.state, "tickers", {}).get(symbol) or {}
                return float(t.get("last") or t.get("price") or 0.0)
        except Exception:
            pass
        return 0.0

    def _round_price_qty(self, price: float, qty: float) -> tuple[float, float]:
        rp = round(float(price or 0.0), 6)
        rq = round(float(qty or 0.0), 6)
        return rp, rq

    def _journal_trade(self, event: Dict[str, Any]) -> None:
        """Записать событие в trades.jsonl (только SIM)."""
        if self.mode != "SIM":
            return
        ev = dict(event)
        ev.setdefault("ts", int(time.time() * 1000))
        _append_jsonl(self.journal_path, ev)

    # -------- API used by UIAPI --------
    def preview_order(self, symbol: str, side: str, qty: float, price: Optional[float] = None, type_: str = "MARKET") -> Preview:
        """Грубый preview: только округление цены/количества и базовая проверка qty>0.

        UIAPI вызывает это перед real/dry-run, чтобы показать округлённые значения.
        """
        side = (side or "BUY")
        qty = float(qty or 0.0)
        if price is None:
            price = self._last_price(symbol)

        rp, rq = self._round_price_qty(price, qty)
        if rq <= 0:
            return Preview(ok=False, reason="qty<=0", info=f"side={side}", rounded_price=rp, rounded_qty=rq)

        info = f"side={side}, type={type_}"
        return Preview(ok=True, reason="", info=info, rounded_price=rp, rounded_qty=rq)

    def place_order(self, symbol: str, side: str, qty: float, type_: str = "MARKET", price: Optional[float] = None) -> OrderResult:
        """Основной вход для UIAPI и TPSLManager.

        - Работает только в не-REAL режимах.
        - Делает dry-run через core.orders.place_order.
        - Пишет событие в trades.jsonl (SIM).
        """
        _ensure_not_real(self.mode)
        from core.orders import place_order as _place_order

        side = (side or "BUY").upper()
        qty = float(qty or 0.0)
        if price is None:
            price = self._last_price(symbol)

        rp, rq = self._round_price_qty(price, qty)

        # Вызов DRY-ордер-плейсера
        raw = _place_order(side=side, symbol=symbol, price=rp, qty=rq, mode=self.mode)

        # Журнал
        self._journal_trade(
            {
                "type": "ORDER",
                "mode": self.mode,
                "symbol": symbol.upper(),
                "side": side,
                "qty": rq,
                "price": rp,
                "status": str(raw.get("status", "")),
                "order_id": raw.get("orderId"),
                "source": "UIAPI",
                "order_type": type_,
            }
        )

        # NEW: обновляем TradeBook в StateEngine (если доступен)
        try:
            state = getattr(self, "state", None)
            if state is not None and hasattr(state, "tradebook") and state.tradebook is not None:
                if side == "BUY":
                    # открытие позиции
                    state.tradebook.open(symbol.upper(), rp, rq, side="BUY")
                elif side == "SELL":
                    # закрытие позиции по SELL
                    state.tradebook.close(symbol.upper(), rp, reason="SELL")
        except Exception:
            # журнал сделок не должен ломать Executor
            pass

        return OrderResult(price=rp, qty=rq, raw=raw)

    def buy_market(self, symbol: str, qty: float) -> OrderResult:
        """Упрощённый шорткат для BUY MARKET (не используется напрямую UI, но оставлен для совместимости)."""
        return self.place_order(symbol=symbol, side="BUY", qty=qty, type_="MARKET")

    def close_position(self, symbol: str, reason: str = "manual") -> Dict[str, Any]:
        """Событие закрытия позиции без фактического ордера (для будущих расширений).

        Сейчас UIAPI для закрытия использует TPSLManager, поэтому здесь — только
        фиксация события в журнале (если понадобится).
        """
        _ensure_not_real(self.mode)
        ts = int(time.time() * 1000)
        event = {"event": "CLOSE", "symbol": symbol, "reason": reason, "ts": ts, "mode": self.mode}
        self._journal_trade({"type": "CLOSE_EVENT", **event})
        return event

    def panic(self, symbol: str) -> OrderResult:
        """Паник-селл через MARKET SELL и запись в журнал."""
        _ensure_not_real(self.mode)
        from core.orders import place_order as _place_order

        price = self._last_price(symbol)
        rp, rq = self._round_price_qty(price, 0.0)

        raw = _place_order(side="SELL", symbol=symbol, price=rp, qty=rq, mode=self.mode)

        self._journal_trade(
            {
                "type": "PANIC",
                "mode": self.mode,
                "symbol": symbol.upper(),
                "side": "SELL",
                "qty": rq,
                "price": rp,
                "status": str(raw.get("status", "")),
                "order_id": raw.get("orderId"),
                "source": "UIAPI",
            }
        )

        # NEW: паник-селл тоже закрывает позицию в TradeBook
        try:
            state = getattr(self, "state", None)
            if state is not None and hasattr(state, "tradebook") and state.tradebook is not None:
                state.tradebook.close(symbol.upper(), rp, reason="PANIC")
        except Exception:
            pass

        return OrderResult(price=rp, qty=rq, raw=raw)


def execute_dry_run(side: str, symbol: str, price: float, qty: float, mode: str = "SIM") -> Dict[str, Any]:
    """Legacy-функция для старых CLI/тестов.

    Делает только вызов core.orders.place_order с защитой от REAL.
    Журнал не пишется, чтобы не дублировать записи относительно OrderExecutor.
    """
    _ensure_not_real(mode)
    from core.orders import place_order
    return place_order(side=side, symbol=symbol, price=price, qty=qty, mode=mode)
