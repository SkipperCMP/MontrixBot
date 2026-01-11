"""TradeBook — простой журнал сделок для UI.

Задачи:
- хранить открытые позиции (по символам);
- фиксировать закрытые сделки с расчётом PnL;
- отдавать список строк в формате, совместимом с DealsJournal.
"""

from __future__ import annotations

import time
from typing import Dict, List, Any, Optional


class TradeBook:
    """Мини-журнал сделок для UI.

    Формат строки (совместим с DealsJournal.update):
        {
            "time": str,
            "symbol": str,
            "tier": int | str,
            "action": str,   # BUY / SELL / PANIC / CLOSE / ...
            "tp": float | None,
            "sl": float | None,
            "pnl_pct": float | None,
            "pnl_abs": float | None,
            "qty": float | None,
            "entry": float | None,
            "exit": float | None,
        }
    """

    def __init__(self) -> None:
        # открытые позиции по символам
        self._open: Dict[str, Dict[str, Any]] = {}
        # закрытые сделки (история)
        self._closed: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _now_ts() -> int:
        return int(time.time())

    @staticmethod
    def _fmt_time(ts: Optional[int]) -> str:
        if not ts:
            ts = int(time.time())
        try:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
        except Exception:
            return str(ts)

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #

    def reset(self) -> None:
        """Полная очистка журнала."""
        self._open.clear()
        self._closed.clear()

    def open(self, symbol: str, price: float, qty: float, side: str = "BUY") -> None:
        """Зафиксировать открытие позиции.

        Используется, когда UIAPI/Executor делает BUY (SIM / DRY).
        """
        try:
            sym = (symbol or "").upper()
            side_u = (side or "BUY").upper()
            price_f = float(price)
            qty_f = float(qty)
        except Exception:
            return

        ts = self._now_ts()

        # Простейшая логика tier: если по символу уже была открытая позиция —
        # увеличиваем tier, иначе ставим 1.
        prev = self._open.get(sym)
        if prev is not None:
            try:
                tier = int(prev.get("tier", 1)) + 1
            except Exception:
                tier = 2
        else:
            tier = 1

        self._open[sym] = {
            "symbol": sym,
            "side": side_u,
            "qty": qty_f,
            "entry": price_f,
            "ts_open": ts,
            "tier": tier,
            # tp/sl пока не считаем — резерв на будущее
            "tp": None,
            "sl": None,
        }

    def close(self, symbol: str, price: float, reason: str = "CLOSE") -> None:
        """Зафиксировать закрытие позиции + добавить строку в историю.

        Вызывается при SELL / PANIC и т.п.
        """
        try:
            sym = (symbol or "").upper()
            price_f = float(price)
        except Exception:
            return

        ts = self._now_ts()
        pos = self._open.pop(sym, None)

        entry: Optional[float] = None
        qty: Optional[float] = None
        side: str = "BUY"
        tier: Any = "-"
        pnl_cash: Optional[float] = None
        pnl_pct: Optional[float] = None

        if pos is not None:
            entry = pos.get("entry")
            qty = pos.get("qty")
            side = str(pos.get("side", "BUY")).upper()
            tier = pos.get("tier", "-")

            try:
                entry_f = float(entry) if entry is not None else None
                qty_f = float(qty) if qty is not None else None
            except Exception:
                entry_f = None
                qty_f = None

            if entry_f and qty_f:
                try:
                    if side.startswith("SHORT") or side == "SELL":
                        pnl_cash = (entry_f - price_f) * qty_f
                    else:
                        pnl_cash = (price_f - entry_f) * qty_f
                    if entry_f != 0:
                        pnl_pct = (pnl_cash / (entry_f * qty_f)) * 100.0
                except Exception:
                    pnl_cash = None
                    pnl_pct = None

        time_str = self._fmt_time(ts)

        row = {
            "time": time_str,
            "symbol": sym,
            "tier": tier,
            "action": (reason or "CLOSE").upper(),
            "tp": pos.get("tp") if pos else None,
            "sl": pos.get("sl") if pos else None,
            "pnl_pct": pnl_pct,
            "pnl_abs": pnl_cash,
            "qty": qty,
            "entry": entry,
            "exit": price_f,
        }

        self._closed.append(row)

    def export_rows(self, max_rows: int = 300) -> List[Dict[str, Any]]:
        """Вернуть строки для DealsJournal.

        Возвращает:
        - все закрытые сделки (ограничение max_rows);
        - плюс действующие открытые позиции как строки с action="OPEN".
        """
        rows: List[Dict[str, Any]] = []

        # закрытые сделки (история)
        rows.extend(self._closed[-max_rows:])

        # открытые позиции как псевдо-сделки (чтобы были видны в журнале)
        for sym, pos in self._open.items():
            ts_open = pos.get("ts_open") or self._now_ts()
            time_str = self._fmt_time(int(ts_open))

            rows.append(
                {
                    "time": time_str,
                    "symbol": sym,
                    "tier": pos.get("tier", "-"),
                    "action": "OPEN",
                    "tp": pos.get("tp"),
                    "sl": pos.get("sl"),
                    "pnl_pct": None,
                    "pnl_abs": None,
                    "qty": pos.get("qty"),
                    "entry": pos.get("entry"),
                    "exit": None,
                }
            )

        if len(rows) > max_rows:
            rows = rows[-max_rows:]

        return rows
