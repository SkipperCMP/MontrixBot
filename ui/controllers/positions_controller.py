from __future__ import annotations

from typing import Any, Callable


class PositionsController:
    """Контроллер панели активных позиций (Active position (SIM)).

    Вынесен из ui.app_step9.App._update_active_from_sim в отдельный модуль
    в рамках STEP1.3.1 (UI splitting).

    Задачи:
    - собрать список активных позиций из AUTOSIM snapshot + UIAPI snapshot
    - посчитать PnL / Value / Hold / маркеры тренда
    - передать готовый текст в App._set_active_text()
    """

    def __init__(self, app: Any, uiapi_getter: Callable[[], Any] | None = None) -> None:
        self.app = app
        self._uiapi_getter = uiapi_getter

    def _get_uiapi(self) -> Any | None:
        if self._uiapi_getter is None:
            return None
        try:
            return self._uiapi_getter()
        except Exception:
            return None

    def update_from_snapshot(self, snapshot: dict) -> None:
        """
        Update Active Position panel.

        CONTRACT (input snapshot):
        - snapshot: dict
          - snapshot["active"]: Optional[list[dict]]
              AUTOSIM fallback positions (legacy path).

        CORE PATH (preferred):
        - UIAPI.get_state_snapshot() -> dict with:
            - "positions": dict[symbol -> position]
            - "ticks": dict[symbol -> { "last": float }]

        SELECTION RULE:
        - core positions are used if present
        - otherwise AUTOSIM snapshot["active"] is used

        OUTPUT:
        - formatted text table passed to App._set_active_text()
        - controller MUST NOT raise; failures are best-effort
        """
        # --- базовый active от AUTOSIM (старое поведение) ---
        try:
            autosim_active = snapshot.get("active") or []
        except Exception:
            autosim_active = []

        # --- пробуем собрать active из ядра (TPSL + StateEngine) ---
        core_active = []
        try:
            api = self._get_uiapi()
            if api is not None and hasattr(api, "get_state_snapshot"):
                se_snap = api.get_state_snapshot() or {}
                positions = se_snap.get("positions") or {}
                ticks = se_snap.get("ticks") or {}

                for sym, pos in positions.items():
                    try:
                        sym_u = str(sym or "").upper()
                        side = str(pos.get("side", "") or "")
                        qty = float(pos.get("qty", 0.0) or 0.0)
                        entry = float(pos.get("entry", 0.0) or 0.0)

                        tick = ticks.get(sym_u, {}) or {}
                        last_raw = tick.get("last", entry)
                        try:
                            last = float(last_raw)
                        except Exception:
                            last = entry

                        pnl_pct = float(pos.get("unrealized_pnl_pct", 0.0) or 0.0)
                        if pnl_pct == 0.0:
                            try:
                                side_u = side.upper()
                                if side_u.startswith("LONG") or side_u == "BUY":
                                    if entry != 0.0:
                                        pnl_pct = (last - entry) / entry * 100.0
                                elif side_u.startswith("SHORT") or side_u == "SELL":
                                    if entry != 0.0:
                                        pnl_pct = (entry - last) / entry * 100.0
                            except Exception:
                                pass

                        core_active.append(
                            {
                                "symbol": sym_u,
                                "side": side,
                                "qty": qty,
                                "entry_price": entry,
                                "current_price": last,
                                "unrealized_pnl_pct": pnl_pct,
                                "tp": float(pos.get("tp", 0.0) or 0.0),
                                "sl": float(pos.get("sl", 0.0) or 0.0),
                                # hold_days пока не считаем для TPSL-позиций
                                "hold_days": float(0.0),
                            }
                        )
                    except Exception:
                        continue
        except Exception:
            core_active = []

        # --- объединяем источники: ядро + AUTOSIM ---
        # Цель: показывать ВСЕ активные позиции.
        # Приоритет: core-строка перекрывает autosim-строку того же symbol.
        merged_by_symbol: dict[str, dict] = {}

        try:
            for p in autosim_active or []:
                sym = str((p or {}).get("symbol") or "").upper()
                if sym:
                    merged_by_symbol[sym] = dict(p)
        except Exception:
            pass

        try:
            for p in core_active or []:
                sym = str((p or {}).get("symbol") or "").upper()
                if sym:
                    merged_by_symbol[sym] = dict(p)
        except Exception:
            pass

        active = list(merged_by_symbol.values())

        # если совсем пусто — рисуем дефолтный текст
        if not active:
            try:
                self.app._set_active_text("— no active positions —")
            except Exception:
                pass
            return

        # --- форматирование вывода в текстовую таблицу ---
        def _format_hold(days: float) -> str:
            """Форматирует hold_days в вид `Xd HH:MM` или `HH:MM`."""
            try:
                total_minutes = int(days * 24 * 60)
            except Exception:
                total_minutes = 0

            if total_minutes <= 0:
                return "—"

            minutes = total_minutes % 60
            hours_total = total_minutes // 60
            days = hours_total // 24
            hours = hours_total % 24

            if days <= 0:
                # только часы:минуты
                return f"{hours:02d}:{minutes:02d}"
            # дни + часы:минуты
            return f"{days}d {hours:02d}:{minutes:02d}"

        lines: list[str] = []
        header = "{:<10} {:<6} {:>9} {:>10} {:>10} {:>10} {:>7} {:>10} {:>10} {:>9} {:>5}".format(
            "Symbol",
            "Side",
            "Qty",
            "Entry",
            "Last",
            "Value",
            "Pnl%",
            "TP",
            "SL",
            "Hold",
            "Trend",
        )
        lines.append(header)
        lines.append("-" * len(header))

        for pos in active:
            symbol = str(pos.get("symbol", ""))
            side = str(pos.get("side", ""))[:6]
            qty = float(pos.get("qty", 0.0) or 0.0)
            entry = float(pos.get("entry_price", 0.0) or 0.0)
            last = float(pos.get("current_price", 0.0) or 0.0)

            # базовый PnL% из снапшота (если есть)
            try:
                pnl_pct = float(pos.get("unrealized_pnl_pct", 0.0) or 0.0)
            except Exception:
                pnl_pct = 0.0

            # перестраховка: если 0 — считаем вручную по side/entry/last
            if pnl_pct == 0.0:
                try:
                    side_u = side.upper()
                    if entry != 0.0:
                        if side_u.startswith("LONG") or side_u == "BUY":
                            pnl_pct = (last - entry) / entry * 100.0
                        elif side_u.startswith("SHORT") or side_u == "SELL":
                            pnl_pct = (entry - last) / entry * 100.0
                except Exception:
                    pass

            # стоимость позиции
            try:
                value = qty * last
            except Exception:
                value = 0.0

            tp = float(pos.get("tp", 0.0) or 0.0)
            sl = float(pos.get("sl", 0.0) or 0.0)
            hold_days = float(pos.get("hold_days", 0.0) or 0.0)
            hold_str = _format_hold(hold_days)

            # маркер тренда по знаку PnL% (используем пули, цвет задаётся тегами)
            if pnl_pct > 0.1:
                trend_mark = "●"
            elif pnl_pct < -0.1:
                trend_mark = "●"
            else:
                trend_mark = "·"

            line = (
                "{:<10} {:<6} {:>9.4f} {:>10.4f} {:>10.4f} {:>10.2f} "
                "{:>7.2f} {:>10.4f} {:>10.4f} {:>9} {:>5}"
            ).format(
                symbol,
                side,
                qty,
                entry,
                last,
                value,
                pnl_pct,
                tp,
                sl,
                hold_str,
                trend_mark,
            )
            lines.append(line)

        try:
            self.app._set_active_text("\n".join(lines))
        except Exception:
            # панель активных позиций не должна ломать основной UI
            return
