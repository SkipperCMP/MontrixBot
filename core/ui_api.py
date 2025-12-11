from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, List

import time

from core.state_engine import StateEngine
from core.executor import OrderExecutor, Preview
from core.tpsl import TPSLManager, TPSSLConfig
from core.state_binder import StateBinder
from core.events import StateSnapshot
from core.runtime_state import load_runtime_state, reset_sim_state
from core.tpsl_settings_api import get_tpsl_settings, update_tpsl_settings


@dataclass
class UIStatus:
    mode: str
    dry_run: bool
    symbols: List[str]
    active_positions: Dict[str, dict]


class UIAPI:
    """
    UIAPI = единый мост между UI (Tkinter) и ядром (StateEngine + TPSL + Executor).

    UI вызывает:
      - set_mode / get_mode / get_status
      - get_state_snapshot()
      - get_last_price(symbol)
      - on_price(symbol, price)
      - update_advisor_snapshot(signal, recommendation, meta)
      - preview / buy_market / close_position / panic
    """

    def __init__(
        self,
        state: StateEngine,
        executor: OrderExecutor,
        tpsl: Optional[TPSLManager] = None,
        symbols: Optional[List[str]] = None,
    ) -> None:
        self.state = state
        self.executor = executor
        self.tpsl = tpsl
        self.symbols = symbols or ["ADAUSDT", "HBARUSDT", "BONKUSDT"]

        # текущий UI-режим
        self._ui_mode: str = "SIM"
        
        # текущий выбранный символ из UI
        self._current_symbol: Optional[str] = None

        # последний advisor-snapshot (signal + recommendation + trend)
        self._advisor_snapshot: Dict[str, Any] = {}
        
        # последние N сигналов/сделок для UI-журналов
        self._recent_signals: List[Dict[str, Any]] = []
        self._recent_trades: List[Dict[str, Any]] = []
        self._max_recent: int = 500

        # StateBinder: единая точка сборки снапшота состояния ядра
        self._snapshot_version: int = 0
        self._binder: Optional[StateBinder] = None
        try:
            self._binder = StateBinder(
                snapshot_provider=self._build_state_snapshot_for_binder,
                patch_callback=None,
                on_resync=None,
            )
        except Exception:
            # если биндер недоступен, UIAPI продолжит работать по старой схеме
            self._binder = None

        # STEP1.3.3: троттлинг для runtime-персистентности
        # (чтобы не писать state.json на каждый тик).
        self._last_runtime_persist_ts: float = 0.0

    # ==============================
    #     УСТАНОВКА РЕЖИМА UI
    # ==============================
    def set_mode(self, mode: str) -> None:
        mode = (mode or "SIM").upper()
        if mode not in ("SIM", "REAL"):
            mode = "SIM"
        self._ui_mode = mode

        # передаём режим в executor
        if hasattr(self.executor, "set_mode"):
            try:
                self.executor.set_mode(mode)
            except Exception:
                pass

        # и в TPSL (если реализовано)
        if self.tpsl is not None and hasattr(self.tpsl, "set_mode"):
            try:
                self.tpsl.set_mode(mode)
            except Exception:
                pass

    def get_mode(self) -> str:
        return self._ui_mode

    def set_current_symbol(self, symbol: str) -> None:
        try:
            self._current_symbol = str(symbol or "").upper()
        except Exception:
            self._current_symbol = None

    def get_current_symbol(self) -> Optional[str]:
        return self._current_symbol

    def get_status(self) -> UIStatus:
        """Краткий статус UI (режим, dry_run, активные позиции)."""
        dry = False
        try:
            dry = bool(getattr(self.executor, "dry_run", False))
        except Exception:
            dry = False

        # активные позиции (из TPSL, если есть)
        positions: Dict[str, dict] = {}
        if self.tpsl is not None:
            try:
                pos_dict = getattr(self.tpsl, "_pos", {})
                for sym, pos in pos_dict.items():
                    qty = float(getattr(pos, "qty", 0.0) or 0.0)
                    entry = float(getattr(pos, "entry_price", 0.0) or 0.0)
                    side = "LONG" if qty >= 0 else "SHORT"
                    positions[str(sym).upper()] = {
                        "side": side,
                        "qty": qty,
                        "entry": entry,
                    }
            except Exception:
                positions = {}

        return UIStatus(
            mode=self._ui_mode,
            dry_run=dry,
            symbols=self.symbols,
            active_positions=positions,
        )
        
    # ==============================
    #   ЖУРНАЛЫ (сигналы/сделки)
    # ==============================
    def _append_bounded(self, storage: List[Dict[str, Any]], row: Dict[str, Any]) -> None:
        """Внутренний хелпер: добавить row и обрезать список до _max_recent."""
        try:
            storage.append(dict(row))
            maxlen = getattr(self, "_max_recent", 500)
            if len(storage) > maxlen:
                del storage[:-maxlen]
        except Exception:
            # в худшем случае просто игнорируем ошибку
            pass

    def add_recent_signal(self, row: Dict[str, Any]) -> None:
        """Добавить запись в журнал сигналов (для UI)."""
        self._append_bounded(self._recent_signals, row)

    def add_recent_trade(self, row: Dict[str, Any]) -> None:
        """Добавить запись в журнал сделок (для UI)."""
        self._append_bounded(self._recent_trades, row)

    # Backward-compatible aliases for older UI code (historical app_step8 AUTOSIM bridge)
    def append_recent_signal(self, row: Dict[str, Any]) -> None:
        """Alias for add_recent_signal (compat with existing UI code)."""
        self.add_recent_signal(row)

    def append_recent_trade(self, row: Dict[str, Any]) -> None:
        """Alias for add_recent_trade (compat with existing UI code)."""
        self.add_recent_trade(row)

    def get_recent_signals(self) -> List[Dict[str, Any]]:
        """Вернуть копию последних сигналов для UI."""
        try:
            return list(self._recent_signals)
        except Exception:
            return []

    def get_recent_trades(self) -> List[Dict[str, Any]]:
        """Вернуть копию последних сделок для UI."""
        try:
            return list(self._recent_trades)
        except Exception:
            return []

    # ==============================
    #      СНАПШОТ СОСТОЯНИЯ
    # ==============================
    
    def _build_state_payload(self) -> Dict[str, Any]:
        """
        Универсальный снапшот для UI.

        Базовая совместимость (как раньше):
            ticks
            positions
            equity
            mode / dry_run
            advisor { side, strength, trend, reason, ... }
            trend

        Дополнительно для STEP1.8+:
            portfolio {
                equity,
                pnl_day_pct,
                pnl_total_pct,
                open_positions_count,
                open_pnl_abs,   # суммарный незакрытый PnL по всем позициям ($) или None
                open_pnl_pct,   # тот же PnL в %% от вложенного капитала или None
            }
            health { status, messages, last_tick_at, latency_ms }
            ts (unix timestamp)
            signals_recent / trades_recent

        """
        # --- 1) Снапшот StateEngine ---
        core_snap: Dict[str, Any] = {}
        try:
            raw = self.state.snapshot()
            if isinstance(raw, dict):
                core_snap = raw
        except Exception:
            core_snap = {}

        ticks = core_snap.get("ticks") or {}
        version = core_snap.get("version", 0)

        # --- 2) Позиции TPSL ---
        positions: Dict[str, dict] = {}
        equity: Optional[float] = None

        if self.tpsl is not None:
            try:
                pos_dict = getattr(self.tpsl, "_pos", {})
                for sym, pos in pos_dict.items():
                    qty = float(getattr(pos, "qty", 0.0) or 0.0)
                    entry = float(getattr(pos, "entry_price", 0.0) or 0.0)
                    side = "LONG" if qty >= 0 else "SHORT"

                    positions[str(sym).upper()] = {
                        "side": side,
                        "qty": qty,
                        "entry": entry,
                        "tp": getattr(pos, "tp_price", None),
                        "sl": getattr(pos, "sl_price", None),
                        "trailing": bool(getattr(pos, "trailing_active", False)),
                    }
            except Exception:
                positions = {}

            # equity из TPSL
            try:
                equity = float(getattr(self.tpsl, "equity"))
            except Exception:
                equity = None

        # fallback: equity можно попытаться взять из core_snap
        if equity is None:
            try:
                eq_raw = core_snap.get("equity")
                if eq_raw is not None:
                    equity = float(eq_raw)
            except Exception:
                equity = None

        # --- 3) Advisor snapshot ---
        advisor = self._advisor_snapshot or {}
        trend = advisor.get("trend")

        # --- 4) Portfolio-блок для UI ---
        def _safe_float(obj: Any) -> Optional[float]:
            try:
                if obj is None:
                    return None
                return float(obj)
            except Exception:
                return None

        pnl_day_pct = None
        pnl_total_pct = None

        if self.tpsl is not None:
            try:
                pnl_day_pct = _safe_float(getattr(self.tpsl, "pnl_day_pct", None))
            except Exception:
                pnl_day_pct = None
            try:
                pnl_total_pct = _safe_float(getattr(self.tpsl, "pnl_total_pct", None))
            except Exception:
                pnl_total_pct = None

        if pnl_day_pct is None:
            pnl_day_pct = _safe_float(getattr(self.executor, "pnl_day_pct", None))
        if pnl_total_pct is None:
            pnl_total_pct = _safe_float(getattr(self.executor, "pnl_total_pct", None))

        try:
            open_positions_count = len(positions)
        except Exception:
            open_positions_count = 0

        portfolio: Dict[str, Any] = {
            "equity": equity,
            "pnl_day_pct": pnl_day_pct,
            "pnl_total_pct": pnl_total_pct,
            "open_positions_count": open_positions_count,
            "open_pnl_abs": open_pnl_abs,
            "open_pnl_pct": open_pnl_pct,
        }

        # --- 4.1) Open PnL по открытым позициям (best-effort) ---
        open_pnl_abs: Optional[float] = None
        open_pnl_pct: Optional[float] = None

        try:
            total_pnl = 0.0
            total_notional = 0.0

            # positions: { "SYMBOL": { side, qty, entry, ... }, ... }
            for sym, pos in positions.items():
                try:
                    qty = float(pos.get("qty") or 0.0)
                    entry_price = float(pos.get("entry") or 0.0)
                except Exception:
                    continue

                if qty == 0.0 or entry_price == 0.0:
                    continue

                sym_key = str(sym).upper()
                tinfo = ticks.get(sym_key) or {}
                last_raw = tinfo.get("last")
                if last_raw is None:
                    continue

                try:
                    last_price = float(last_raw)
                except Exception:
                    continue

                # qty уже со знаком: для SHORT отрицательный, формула (last - entry) * qty даёт правильный знак
                pnl = (last_price - entry_price) * qty
                total_pnl += pnl
                total_notional += abs(entry_price * qty)

            if total_notional > 0.0:
                open_pnl_abs = total_pnl
                open_pnl_pct = (total_pnl / total_notional) * 100.0
            else:
                open_pnl_abs = None
                open_pnl_pct = None
        except Exception:
            open_pnl_abs = None
            open_pnl_pct = None

        # --- 5) Health-блок ---
        health: Dict[str, Any] = {
            "status": "OK",
            "messages": [],
        }

        core_health = core_snap.get("health")
        if isinstance(core_health, dict):
            try:
                for k, v in core_health.items():
                    health[k] = v
            except Exception:
                # не критично
                pass

        # Латентность (если есть last_tick_ts в снапшоте state)
        latency_ms: Optional[float] = None
        try:
            last_tick_ts = core_snap.get("last_tick_ts")
            if last_tick_ts:
                now = time.time()
                latency_ms = max(0.0, (now - float(last_tick_ts)) * 1000.0)
        except Exception:
            latency_ms = None

        if latency_ms is not None:
            health["latency_ms"] = latency_ms

        # Финальная сборка снапшота
        snap: Dict[str, Any] = {
            "version": version,
            "mode": self._ui_mode,
            "ticks": ticks,
            "positions": positions,
            "equity": equity,
            "advisor": advisor,
            "trend": trend,
            "portfolio": portfolio,
            "health": health,
            "ts": int(time.time() * 1000),
            # NEW: recent-журналы для UI
            "signals_recent": self.get_recent_signals(),
            "trades_recent": self.get_recent_trades(),
        }
        return snap

    # ==============================
    #   RUNTIME SNAPSHOT ДЛЯ UI
    # ==============================
    def get_runtime_state_snapshot(self) -> Dict[str, Any]:
        """
        Объединённое runtime-состояние (state.json + sim_state.json) для UI.

        UI ничего не знает про файлы: всё идёт через core/runtime_state.
        """
        try:
            return load_runtime_state()
        except Exception:
            return {}

    def maybe_persist_runtime_state(self, snapshot: Optional[Dict[str, Any]] = None) -> None:
        """
        STEP1.3.3 — best-effort runtime-персистентность.

        Вызывается из UI (SnapshotService) не чаще, чем раз в N секунд.
        Обновляет runtime_state на основе UI-снапшота (positions + meta),
        не затрагивая sim-часть.
        """
        # Лёгкий time-based throttle, чтобы не заливать диск.
        try:
            now = time.time()
            last = float(getattr(self, "_last_runtime_persist_ts", 0.0))
            # не чаще раза в 5 секунд
            if now - last < 5.0:
                return
        except Exception:
            # если что-то пошло не так, не даём этому сломать UI
            pass

        if snapshot is None:
            try:
                snapshot = self.get_state_snapshot()
            except Exception:
                return

        if not isinstance(snapshot, dict):
            return

        # Импортируем здесь, чтобы избежать циклов импортов.
        try:
            from core.runtime_persistence import persist_from_ui_snapshot
        except Exception:
            return

        try:
            persist_from_ui_snapshot(snapshot)
            self._last_runtime_persist_ts = time.time()
        except Exception:
            # любые ошибки на этом пути не должны ломать UI
            pass

    def reset_sim_state(self) -> None:
        """
        Запрос от UI на полный сброс SIM-состояния.

        UI не трогает файлы напрямую: всё идёт через core.runtime_state.reset_sim_state().
        """
        try:
            reset_sim_state()
        except Exception:
            # Ошибки при сбросе SIM не должны ломать UI.
            pass
    
    # ==============================
    #            ХУКИ UI
    # ==============================
    def _build_state_snapshot_for_binder(self) -> StateSnapshot:
        """
        Внутренний snapshot-provider для StateBinder.

        Собирает payload тем же способом, что и _build_state_payload,
        и оборачивает его в StateSnapshot с монотонно растущей версией.
        """
        try:
            payload = self._build_state_payload()
        except Exception:
            payload = {}
        self._snapshot_version = int(getattr(self, "_snapshot_version", 0) + 1)
        return StateSnapshot(version=self._snapshot_version, payload=payload)

    def get_state_snapshot(self) -> Dict[str, Any]:
        """
        Универсальный снапшот для UI.

        Если StateBinder доступен, снапшот берётся через него,
        иначе используется прямой сбор payload (как в прошлых версиях).
        """
        binder = getattr(self, "_binder", None)
        if binder is None:
            # fallback: поведение как до интеграции StateBinder
            return self._build_state_payload()

        try:
            # Для текущей версии мы просто делаем полную синхронизацию
            # при каждом запросе снапшота. В будущем сюда можно добавить
            # поддержку инкрементальных StatePatch и Heartbeat.
            binder.init_or_resync()
            snap = binder.get_ui_state()
            if isinstance(snap, dict):
                return snap
        except Exception:
            # На всякий случай не ломаем UI — возвращаем прямой снапшот.
            pass

        return self._build_state_payload()

    def on_price(self, symbol: str, price: float, ts: Optional[float] = None) -> int:
        """
        UI → ядро: проброс последней цены в StateEngine.
        """
        state = self.state
        if not hasattr(state, "upsert_ticker"):
            return 0

        try:
            symbol_u = str(symbol or "").upper()
        except Exception:
            symbol_u = "UNKNOWN"

        try:
            state.upsert_ticker(symbol_u, price, ts=ts)
        except Exception:
            return 0

        return 1

    # ==============================
    #   ADVISOR SNAPSHOT / TREND
    # ==============================
    def update_advisor_snapshot(
        self,
        signal: Optional[Dict[str, Any]],
        recommendation: Optional[Dict[str, Any]],
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        UI вызывает это, когда есть новый сигнал/рекомендация от Advisor.
        """
        snap: Dict[str, Any] = {}
        snap["signal"] = signal or {}
        snap["recommendation"] = recommendation or {}
        snap["meta"] = meta or {}
        try:
            trend = snap["recommendation"].get("trend")
        except Exception:
            trend = None
        if trend is not None:
            snap["trend"] = trend
        self._advisor_snapshot = snap

    # ==============================
    #  GET LAST PRICE / PREVIEW / BUY
    # ==============================
    def get_last_price(self, symbol: Optional[str] = None) -> Optional[float]:
        """
        Получить последнюю цену по symbol из StateEngine.
        Если symbol не передан, используем текущий symbol из UI (set_current_symbol).
        """
        if symbol is None:
            symbol = self._current_symbol

        if not symbol:
            return None

        try:
            symbol_u = str(symbol or "").upper()
        except Exception:
            return None

        try:
            snap = self.state.snapshot() or {}
            ticks = snap.get("ticks") or {}
            tick = ticks.get(symbol_u) or {}
            last = tick.get("last")
            if last is None:
                return None
            return float(last)
        except Exception:
            return None

    # ==============================
    #   TPSL SETTINGS ДЛЯ UI
    # ==============================
    def get_tpsl_settings_for_ui(self) -> Dict[str, Any]:
        """
        Отдать UI текущие TPSL-настройки.

        UI получает только dict, без знания о runtime-файлах.
        """
        try:
            return get_tpsl_settings()
        except Exception:
            # на уровне UIAPI возвращаем безопасный default
            return {}

    def update_tpsl_settings_from_ui(self, settings: Dict[str, Any]) -> None:
        """
        Обновить TPSL-настройки по запросу UI.
        """
        try:
            update_tpsl_settings(settings)
        except Exception:
            # ошибки сохранения настроек не должны ронять UI
            pass

    def preview(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: Optional[float] = None,
    ) -> Optional[Preview]:
        """
        Запрос предварительного расчёта сделки (Preview) у executor.

        Аргументы:
            symbol: торговая пара (например, ADAUSDT)
            side: "BUY" или "SELL"
            qty: желаемое количество
            price: опциональная цена; если None, executor сам возьмёт last_price
        """
        # OrderExecutor предоставляет preview_order, а не preview
        if not hasattr(self.executor, "preview_order"):
            return None
        try:
            return self.executor.preview_order(
                symbol=symbol,
                side=side,
                qty=qty,
                price=price,
            )
        except Exception:
            return None


    def buy_market(
        self,
        symbol: str,
        qty: float,
        side: str = "BUY",
        reason: str = "UI",
        tpsl_cfg: Optional[TPSSLConfig] = None,
    ) -> bool:
        """
        Отправка рыночного ордера через executor.
        """
        # Используем основной вход executor.place_order, он уже делает DRY-run и логирует
        if not hasattr(self.executor, "place_order"):
            return False

        try:
            _res = self.executor.place_order(
                symbol=symbol,
                side=side,
                qty=qty,
                type_="MARKET",
            )
        except Exception:
            return False

        # TPSL-обёртка (если есть)
        if self.tpsl is not None and tpsl_cfg is not None:
            try:
                self.tpsl.attach(symbol, tpsl_cfg)
            except Exception:
                pass

        return True


    # ==============================
    #     ЗАКРЫТИЕ ПОЗИЦИЙ / PANIC
    # ==============================
    def close_position(self, symbol: str, reason: str = "UI_close") -> None:
        """
        Ручное закрытие позиции из UI (через TPSL).
        """
        if self.tpsl is not None:
            try:
                self.tpsl.close(symbol.upper(), reason)
            except Exception:
                pass

    def panic(self, symbol: str) -> None:
        """
        Паник-селл из UI.
        """
        if self.tpsl is not None:
            try:
                self.tpsl.close(symbol.upper(), "UI_panic")
            except Exception:
                pass
