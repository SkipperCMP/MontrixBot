from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Optional

from ui.state.ui_state import UIState


class AutosimController:
    """Контроллер AUTOSIM на уровне UI.

    STEP1.3.1: первый вынос логики работы с AUTOSIM из ui.app_step9.
    На этом под-шаге переносим только ручное закрытие позиций
    `_manual_close_sim_position`, чтобы разгрузить App.
    """

    def __init__(
        self,
        app: Any,
        ui_state: Optional[UIState] = None,
        uiapi_getter: Optional[Callable[[], Any]] = None,
        save_sim_state_fn: Optional[Callable[[dict], None]] = None,
        journal_file: Optional[Path] = None,
    ) -> None:
        self.app = app
        self.ui_state = ui_state
        self._uiapi_getter = uiapi_getter
        self._save_sim_state = save_sim_state_fn
        self._journal_file = journal_file

    # ------------------------------------------------------------------ helpers

    def _get_uiapi(self) -> Any | None:
        getter = self._uiapi_getter
        if getter is None:
            return None
        try:
            return getter()
        except Exception:
            return None

    def _get_autosim_engine(self) -> Any | None:
        """Возвращает движок AUTOSIM (engine), если он активен."""
        try:
            sim = getattr(self.app, "_autosim", None)
        except Exception:
            sim = None
        if sim is None:
            return None

        try:
            engine = getattr(sim, "engine", None)
        except Exception:
            engine = None
        return engine

    def _log(self, msg: str) -> None:
        try:
            log_fn = getattr(self.app, "_log", None)
            if callable(log_fn):
                log_fn(msg)
        except Exception:
            # лог не должен ломать контроллер
            return

    # ---------------------------------------------------------------- autosim --

    def manual_close_sim_position(self, symbol: str, reason: str = "UI_CLOSE") -> None:
        """Закрывает все позиции по symbol в AUTOSIM и пишет SELL в журнал.

        Это прямой перенос логики из App._manual_close_sim_position с минимальной
        адаптацией под контроллер (используем self.app и внедрённые зависимости).
        """
        engine = self._get_autosim_engine()
        if engine is None:
            return

        # нормализуем символ
        try:
            sym_u = (symbol or "").upper()
        except Exception:
            sym_u = symbol or ""

        # собираем все открытые позиции по этому символу
        positions = []
        try:
            for p in list(getattr(engine, "active_positions", []) or []):
                try:
                    if (p.get("symbol") or "").upper() == sym_u:
                        positions.append(p)
                except Exception:
                    continue
        except Exception:
            positions = []

        if not positions:
            return

        self._log(f"[AUTOSIM] manual_close: found {len(positions)} positions for {sym_u}")

        # получаем последнюю цену из UIAPI/state
        last_price = None
        try:
            api = self._get_uiapi()
            if api is not None and hasattr(api, "get_last_price"):
                last_price = api.get_last_price(sym_u)
        except Exception:
            last_price = None

        lp: Optional[float] = None

        # 1) пробуем цену из UIAPI
        if last_price is not None:
            try:
                lp = float(last_price)
            except Exception:
                lp = None

        # 2) если UIAPI ничего не знает — берём цену из позиции AUTOSIM
        if lp is None or lp <= 0.0:
            try:
                first_pos = positions[0]
                candidate = first_pos.get("current_price") or first_pos.get("entry_price")
                if candidate is not None:
                    lp = float(candidate)
            except Exception:
                lp = None

        # 3) если после всех попыток цена всё ещё невалидна — выходим
        if lp is None or lp <= 0.0:
            self._log(f"[AUTOSIM] manual_close: no valid last_price for {sym_u}, cancel")
            return

        # закрываем все найденные позиции в AUTOSIM и сами считаем PnL для журнала
        records: list[dict[str, Any]] = []

        for pos in positions:
            # безопасно достаём основные поля позиции
            try:
                side_pos = str(pos.get("side", "")).upper()
                qty = float(pos.get("qty") or 0.0)
                entry = float(pos.get("entry_price") or 0.0)
            except Exception:
                continue

            # если позиция "битая" — закрываем, но без записи в журнал
            if qty <= 0.0 or entry <= 0.0:
                try:
                    sim_obj = getattr(self.app, "_autosim", None)
                    if sim_obj is not None and hasattr(sim_obj, "_close_position"):
                        sim_obj._close_position(pos, lp, reason=reason)
                except Exception:
                    pass
                continue

            # вызываем закрытие в движке AUTOSIM, чтобы он обновил equity / active_positions
            try:
                sim_obj = getattr(self.app, "_autosim", None)
                if sim_obj is not None and hasattr(sim_obj, "_close_position"):
                    sim_obj._close_position(pos, lp, reason=reason)
            except Exception:
                # даже если он ничего не вернул — журнал мы всё равно запишем
                pass

            # вычисляем сторону закрытия и PnL
            if side_pos in ("SHORT", "SELL"):
                close_side = "BUY"
                pnl_cash = (entry - lp) * qty
            else:
                # считаем, что любая неявная позиция — LONG/BUY
                close_side = "SELL"
                pnl_cash = (lp - entry) * qty

            notional = entry * qty
            pnl_pct = (pnl_cash / notional * 100.0) if notional else 0.0

            # оценка времени удержания из hold_days (если есть)
            hold_seconds = None
            try:
                hold_days = float(pos.get("hold_days", 0.0) or 0.0)
                hold_seconds = int(hold_days * 86400)
            except Exception:
                pass

            rec: dict[str, Any] = {
                "type": "ORDER",
                "mode": "SIM",
                "symbol": pos.get("symbol"),
                "side": close_side,
                "qty": qty,
                "price": lp,
                "status": "FILLED",
                "ts": int(time.time()),
                "source": reason,
                "pnl_cash": pnl_cash,
                "pnl_pct": pnl_pct,
            }
            if hold_seconds is not None:
                rec["hold_seconds"] = hold_seconds

            records.append(rec)

        if not records:
            return

        # пишем все SELL в журнал одной пачкой
        jf = self._journal_file
        if jf is not None:
            try:
                jf.parent.mkdir(parents=True, exist_ok=True)
                with jf.open("a", encoding="utf-8") as f:
                    for rec in records:
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            except Exception:
                # не даём ошибкам журнала ломать UI
                pass

        # после ручного закрытия руками обновляем snapshot для UI,
        # чтобы Active position (SIM) и мини-equity обновились сразу
        try:
            active_now = list(getattr(engine, "active_positions", []) or [])

            portfolio = {
                "equity": float(getattr(engine, "equity", 0.0) or 0.0),
                "cash": float(getattr(engine, "cash", 0.0) or 0.0),
                "open_positions_count": len(active_now),
            }

            snapshot = {
                "portfolio": portfolio,
                "active": active_now,
            }

            # обновляем панель активных позиций
            try:
                self.app._update_active_from_sim(snapshot)
            except Exception:
                pass

            # обновляем мини-equity бар
            try:
                self.app._update_equity_bar(snapshot)
            except Exception:
                pass

            # перезаписываем sim_state.json для консистентности (атомарно)
            if self._save_sim_state is not None:
                try:
                    self._save_sim_state(snapshot)
                except Exception:
                    pass
        except Exception:
            # любые ошибки здесь не должны ломать UI
            pass

    # пока оставляем заглушку для дальнейшей интеграции c topbar
    def bind_to_topbar(self, topbar_view: Any) -> None:
        """Привязка кнопок Start/Stop AUTOSIM к виджету topbar.

        Реализуем на следующих под-шагах STEP1.3.x, когда topbar будет
        полностью вынесен из app_step9.
        """
        # TODO: перенести сюда реальные биндинги из App, когда topbar
        # будет вынесен в отдельный виджет.
        return
