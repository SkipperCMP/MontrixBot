from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
#  Конфиг авто-симулятора
# ---------------------------------------------------------------------------


@dataclass
class AutoSimConfig:
    # стартовый депозит
    initial_equity: float = 1000.0

    # сколько рискаем на одну сделку (доля от equity)
    risk_per_trade: float = 0.02  # 2%

    # базовые TP/SL в процентах от входа
    tp_pct: float = 4.0           # +4% профит
    sl_pct: float = 3.0           # -3% убыток

    # когда включаем трейлинг (по профиту)
    trail_activate_pct: float = 2.0   # активируем трейл при +2%
    trail_step_pct: float = 1.0       # SL тянем на 1% ниже текущей цены

    # максимально допустимое количество одновременно открытых позиций
    max_open_positions: int = 1

log = logging.getLogger("montrix.autosim")
_log_throttle: dict[str, float] = {}

def _log_throttled(key: str, msg: str, *, interval_s: float = 60.0) -> None:
    try:
        now = time.time()
        last = _log_throttle.get(key, 0.0)
        if now - last < interval_s:
            return
        _log_throttle[key] = now
        log.exception(msg)
    except Exception:
        return

# ---------------------------------------------------------------------------
#  Внутренний движок
# ---------------------------------------------------------------------------


class AutoSimEngine:
    def __init__(self, config: AutoSimConfig) -> None:
        self.config = config
        self.active_positions: List[Dict[str, Any]] = []
        self.closed_trades: List[Dict[str, Any]] = []

        # считаем, что equity = кэш, пока нет позиций
        self.cash: float = config.initial_equity
        self.equity: float = config.initial_equity

        # дневной контроль equity: точка старта дня и индекс дня (UTC)
        try:
            self._day_index: int = int(self._now() // 86400)
        except Exception:
            log.warning("autosim: failed to init day index; defaulting to 0")
            self._day_index = 0
        self.day_start_equity: float = float(self.equity)

    # ----------------- helpers -----------------

    def _signal_side(self, simple_signal: Any) -> Optional[str]:
        """Достаём side из simple_signal (dataclass / dict)."""
        if simple_signal is None:
            return None
        side = None
        if hasattr(simple_signal, "side"):
            side = getattr(simple_signal, "side", None)
        if side is None and isinstance(simple_signal, dict):
            side = simple_signal.get("side")
        if isinstance(side, str):
            side = side.upper()
        return side

    def _reco_side(self, reco: Any) -> Optional[str]:
        if reco is None:
            return None
        side = reco.get("side") if isinstance(reco, dict) else None
        if isinstance(side, str):
            side = side.upper()
        return side

    def _now(self) -> float:
        return time.time()

    def _recalc_equity(self) -> None:
        eq = self.cash
        for pos in self.active_positions:
            try:
                eq += float(pos.get("current_price", 0.0) or 0.0) * float(
                    pos.get("qty", 0.0) or 0.0
                )
            except Exception:
                _log_throttled("recalc_equity_pos", "autosim: failed to recalc equity for position")
        self.equity = float(eq)

        # если наступил новый день (UTC) — обновляем точку старта дня
        try:
            cur_day = int(self._now() // 86400)
        except Exception:
            cur_day = None

        try:
            if cur_day is not None:
                if getattr(self, "_day_index", None) is None:
                    self._day_index = cur_day
                    self.day_start_equity = float(self.equity)
                elif cur_day != self._day_index:
                    self._day_index = cur_day
                    # фиксируем equity на начало нового дня
                    self.day_start_equity = float(self.equity)
        except Exception:
            _log_throttled("day_rollover", "autosim: failed day rollover update")
            # в случае любой ошибки не ломаем симулятор
            return

    # ----------------- позиция -----------------

    def _open_long(self, symbol: str, price: float) -> Optional[Dict[str, Any]]:
        """Открываем LONG-позицию и, если всё прошло успешно,
        возвращаем простое описание ордера для журнала (trades)."""
        if price <= 0.0:
            return None
        if len(self.active_positions) >= self.config.max_open_positions:
            return None

        # риск-на-сделку в деньгах
        risk_cash = self.equity * self.config.risk_per_trade

        # SL ниже входа
        sl_price = price * (1.0 - self.config.sl_pct / 100.0)
        price_diff = price - sl_price
        if price_diff <= 0:
            return None

        # размер позиции по риску
        qty_by_risk = risk_cash / price_diff

        # ограничение по кэшу
        max_qty_by_cash = self.cash / price
        qty = max(0.0, min(qty_by_risk, max_qty_by_cash))
        if qty <= 0.0:
            return None

        tp_price = price * (1.0 + self.config.tp_pct / 100.0)

        now = self._now()
        pos = {
            "symbol": symbol.upper(),
            "side": "LONG",
            "qty": float(qty),
            "entry_price": float(price),
            "current_price": float(price),
            "unrealized_pnl_pct": 0.0,
            "tp": float(tp_price),
            "sl": float(sl_price),
            "trail_active": False,
            "trail_step_pct": float(self.config.trail_step_pct),
            "trail_trigger_pct": float(self.config.trail_activate_pct),
            "opened_ts": now,
            "hold_days": 0.0,
        }
        self.active_positions.append(pos)
        # уменьшаем кэш
        self.cash -= price * qty
        self._recalc_equity()

        # событие ордера BUY для журнала trades
        return {
            "symbol": pos["symbol"],
            "side": "BUY",
            "qty": float(pos["qty"]),
            "price": float(price),
            "status": "FILLED",
            "ts": int(now),
        }

    def _update_position_market(self, pos: Dict[str, Any], last_price: float) -> None:
        if last_price <= 0.0:
            return

        pos["current_price"] = float(last_price)

        entry = float(pos.get("entry_price", 0.0) or 0.0)
        if entry > 0.0:
            pnl_pct = (last_price - entry) / entry * 100.0
        else:
            pnl_pct = 0.0
        pos["unrealized_pnl_pct"] = float(pnl_pct)

        # время удержания в днях
        opened_ts = float(pos.get("opened_ts", self._now()) or self._now())
        pos["hold_days"] = (self._now() - opened_ts) / 86400.0

        # трейлинг SL
        try:
            trail_trigger = float(pos.get("trail_trigger_pct", 0.0) or 0.0)
            trail_step_pct = float(pos.get("trail_step_pct", 0.0) or 0.0)
            sl_price = float(pos.get("sl", 0.0) or 0.0)

            if pnl_pct >= trail_trigger and trail_step_pct > 0.0:
                pos["trail_active"] = True
                # SL тянем на trail_step_pct ниже текущей цены,
                # но не опускаем ниже старого SL
                new_sl = last_price * (1.0 - trail_step_pct / 100.0)
                if new_sl > sl_price:
                    pos["sl"] = new_sl
        except Exception:
            _log_throttled("trail_sl", "autosim: trailing SL update failed")
            return

    def _close_position(
        self,
        pos: Dict[str, Any],
        close_price: float,
        reason: str = "unknown",
    ) -> Optional[Dict[str, Any]]:
        """Закрываем позицию и возвращаем описание ордера SELL для trades."""
        if close_price <= 0.0:
            return None

        qty = float(pos.get("qty", 0.0) or 0.0)
        entry = float(pos.get("entry_price", 0.0) or 0.0)
        pnl_cash = (close_price - entry) * qty
        pnl_pct = (
            (close_price - entry) / entry * 100.0 if entry > 0.0 else 0.0
        )

        # время удержания в секундах (для статистики по сделке)
        opened_ts = float(pos.get("opened_ts", self._now()) or self._now())
        hold_seconds = max(0.0, self._now() - opened_ts)

        trade = dict(pos)
        trade.update(
            {
                "closed_ts": self._now(),
                "close_price": float(close_price),
                "pnl_cash": float(pnl_cash),
                "pnl_pct": float(pnl_pct),
                "close_reason": reason,
                "hold_seconds": float(hold_seconds),
            }
        )
        self.closed_trades.append(trade)

        # событие ордера для журнала trades
        order_event = {
            "symbol": trade.get("symbol"),
            "side": "SELL",
            "qty": float(trade.get("qty", 0.0) or 0.0),
            "price": float(close_price),
            "status": "FILLED",
            "ts": int(self._now()),
            # дублируем ключевые поля PnL/причины, чтобы их можно было
            # сразу писать в trades.jsonl
            "pnl_cash": float(pnl_cash),
            "pnl_pct": float(pnl_pct),
            "reason": reason,
            "hold_seconds": float(hold_seconds),
        }

        # возвращаем кэш
        self.cash += close_price * qty

        # удаляем позицию из активных
        try:
            self.active_positions.remove(pos)
        except ValueError:
            log.debug("autosim: position already removed from active_positions")
        self._recalc_equity()

    # ----------------- основная точка входа -----------------

    def process(
        self,
        symbol: str,
        last_price: Optional[float],
        simple_signal: Any,
        recommendation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Основной цикл авто-SIM.

        Вызывается часто из UI, на каждом тике / обновлении сигналов.
        """
        symbol = (symbol or "").upper()
        last_price = float(last_price or 0.0)

        # события ордеров за текущий тик (для snapshot["trades"])
        trades_tick: List[Dict[str, Any]] = []

        sig_side = self._signal_side(simple_signal)
        reco_side = self._reco_side(recommendation)

        # обновляем все открытые позиции по рынку
        for pos in list(self.active_positions):
            if pos.get("symbol") != symbol:
                continue
            self._update_position_market(pos, last_price)

        # логика открытия / закрытия позиций
        # 1) если позиции нет — можно открыть LONG по BUY-рекомендации
        has_open = any(p.get("symbol") == symbol for p in self.active_positions)

        if not has_open and last_price > 0.0:
            if reco_side == "BUY" or (reco_side is None and sig_side == "BUY"):
                ev = self._open_long(symbol, last_price)
                if ev is not None:
                    trades_tick.append(ev)

        # 2) если позиция есть — проверяем TP/SL/рекомендацию SELL
        for pos in list(self.active_positions):
            if pos.get("symbol") != symbol:
                continue

            cur_price = float(pos.get("current_price", last_price) or last_price)
            tp = float(pos.get("tp", 0.0) or 0.0)
            sl = float(pos.get("sl", 0.0) or 0.0)

            # закрытие по SL
            if sl > 0.0 and cur_price <= sl:
                ev = self._close_position(pos, cur_price, reason="SL")
                if ev is not None:
                    trades_tick.append(ev)
                continue

            # закрытие по TP
            if tp > 0.0 and cur_price >= tp:
                ev = self._close_position(pos, cur_price, reason="TP")
                if ev is not None:
                    trades_tick.append(ev)
                continue

            # закрытие по сильной рекомендации SELL
            if reco_side == "SELL":
                ev = self._close_position(pos, cur_price, reason="RECO_SELL")
                if ev is not None:
                    trades_tick.append(ev)
                continue

        # после всех действий — финальный пересчёт equity
        self._recalc_equity()

        # собираем snapshot для UI
        # базовые поля портфеля
        portfolio = {
            "equity": float(self.equity),
            "cash": float(self.cash),
            "open_positions_count": len(self.active_positions),
        }

        # добавляем PnL в процентах от начального капитала и от старта дня
        try:
            eq = float(self.equity)
            eq0 = float(self.config.initial_equity) if self.config.initial_equity else None
        except Exception:
            _log_throttled("eq_cast", "autosim: failed to cast equity/initial_equity")
            eq = self.equity
            eq0 = None

        try:
            day_start = float(self.day_start_equity)
        except Exception:
            _log_throttled("day_start_cast", "autosim: failed to cast day_start_equity")
            day_start = None

        # общий PnL от initial_equity
        if eq0 and eq0 != 0:
            try:
                portfolio["pnl_total_pct"] = (eq - eq0) / eq0 * 100.0
            except Exception:
                _log_throttled("pnl_total", "autosim: failed to compute pnl_total_pct")
                portfolio["pnl_total_pct"] = 0.0

        # дневной PnL от equity на начало дня
        if day_start and day_start != 0:
            try:
                portfolio["pnl_day_pct"] = (eq - day_start) / day_start * 100.0
            except Exception:
                _log_throttled("pnl_day", "autosim: failed to compute pnl_day_pct")
                portfolio["pnl_day_pct"] = 0.0

        snapshot_active: List[Dict[str, Any]] = []
        for pos in self.active_positions:
            snapshot_active.append(
                {
                    "symbol": pos.get("symbol"),
                    "side": pos.get("side"),
                    "qty": float(pos.get("qty", 0.0) or 0.0),
                    "entry_price": float(pos.get("entry_price", 0.0) or 0.0),
                    "current_price": float(pos.get("current_price", 0.0) or 0.0),
                    "unrealized_pnl_pct": float(
                        pos.get("unrealized_pnl_pct", 0.0) or 0.0
                    ),
                    "tp": float(pos.get("tp", 0.0) or 0.0),
                    "sl": float(pos.get("sl", 0.0) or 0.0),
                    "hold_days": float(pos.get("hold_days", 0.0) or 0.0),
                }
            )

        snapshot: Dict[str, Any] = {
            "ts": int(self._now()),
            "symbol": symbol,
            "last_price": float(last_price),
            "portfolio": portfolio,
            "active": snapshot_active,
            # closed_trades здесь можно не отдавать целиком,
            # но оставляем для future-фич
            "closed_trades": list(self.closed_trades),
            # события ордеров за текущий тик (для журнала trades.jsonl)
            "trades": trades_tick,
        }
        return snapshot


# ---------------------------------------------------------------------------
#  Публичный фасад для UI
# ---------------------------------------------------------------------------


class AutoSimFromSignals:
    """
    Обёртка для использования из UI.

        Исторически в app_step8.py вызывалось так (сейчас — через app_step9):
        AutoSimFromSignals(config=AutoSimConfig())
        ...
        snapshot = autosim.process(symbol, last_price, sig, reco)
    """

    def __init__(self, config: Optional[AutoSimConfig] = None) -> None:
        self.config = config or AutoSimConfig()
        self.engine = AutoSimEngine(self.config)
        # проксируем initial_equity для удобного доступа из UI
        try:
            self.initial_equity: float = float(self.config.initial_equity)
        except Exception:
            log.warning("autosim: initial_equity is not float-castable; keeping raw value")
            self.initial_equity = self.config.initial_equity

    def process(
        self,
        symbol: str,
        last_price: Optional[float],
        simple_signal: Any,
        recommendation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self.engine.process(
            symbol=symbol,
            last_price=last_price,
            simple_signal=simple_signal,
            recommendation=recommendation,
        )

    def reset(self) -> None:
        self.engine = AutoSimEngine(self.config)
