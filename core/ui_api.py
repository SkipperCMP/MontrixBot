from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, List

import time
import threading
import os
import sys
import json
import subprocess
from pathlib import Path

import logging
from core.candles import build_ohlc_from_ticks

log = logging.getLogger(__name__)

# UI forbidden actions registry (SSOT; best-effort import to avoid breaking core)
try:
    from core.ui_forbidden_actions import normalize_ui_action, describe_ui_action  # type: ignore
except Exception:  # pragma: no cover
    def normalize_ui_action(action: str) -> str:  # type: ignore
        try:
            s = str(action or "").strip()
            return s if s else "UNKNOWN_ACTION"
        except Exception:
            return "UNKNOWN_ACTION"

    def describe_ui_action(action: str) -> str:  # type: ignore
        return normalize_ui_action(action)

# Event spine (best-effort)
try:
    from core.event_bus import get_event_bus, make_event, new_cid
except Exception:  # pragma: no cover
    get_event_bus = None  # type: ignore
    make_event = None  # type: ignore
    new_cid = None  # type: ignore
_LOG_THROTTLE: Dict[str, float] = {}

try:
    from tools.ipc_equity import append_equity_point as _append_equity_point  # type: ignore
except Exception:  # pragma: no cover
    _append_equity_point = None  # type: ignore

def _log_throttled(key: str, level: str, msg: str, *, interval_s: float = 60.0, exc_info: bool = False) -> None:
    """
    Throttled logging helper: never raises, never breaks UI/core loop.
    """
    try:
        now = time.time()
        last = float(_LOG_THROTTLE.get(key, 0.0) or 0.0)
        if (now - last) < float(interval_s):
            return
        _LOG_THROTTLE[key] = now
        fn = getattr(log, level, log.warning)
        fn(msg, exc_info=exc_info)
    except Exception:
        return

from core.state_engine import StateEngine
from core.executor import OrderExecutor, Preview
from core.tpsl import TPSLManager, TPSSLConfig
from core.state_binder import StateBinder
from core.events import StateSnapshot
from core.runtime_state import load_runtime_state, reset_sim_state
from core.tpsl_settings_api import get_tpsl_settings, update_tpsl_settings
from core import heartbeats as hb

@dataclass
class UIStatus:
    mode: str
    dry_run: bool
    symbols: List[str]
    active_positions: Dict[str, dict]


def _emit_event(event_type: str, payload: Dict[str, Any], *, actor: str = "ui", cid: str | None = None) -> None:
    try:
        if get_event_bus is None or make_event is None:
            return
        bus = get_event_bus()
        bus.publish(make_event(event_type, payload, actor=actor, cid=cid))
    except Exception:
        return

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
        self.symbols = symbols or ["BTCUSDT", "HBARUSDT", "BONKUSDT"]

        # текущий UI-режим
        self._ui_mode: str = "SIM"

        # UI hardening: по умолчанию UI работает в READ-ONLY режиме
        # (любой write-action через UIAPI будет заблокирован)
        # Override: MB_UI_READ_ONLY=0
        self._ui_read_only: bool = str(os.environ.get("MB_UI_READ_ONLY", "1")).strip().lower() not in (
            "0",
            "false",
            "no",
            "off",
        )

        # текущий выбранный символ из UI
        self._current_symbol: Optional[str] = None

        # последний advisor-snapshot (signal + recommendation + trend)
        self._advisor_snapshot: Dict[str, Any] = {}

        # последняя причина, почему ордер был заблокирован/упал (для UI explain)
        self._last_order_error: Optional[str] = None

        # последние N сигналов/сделок для UI-журналов
        self._recent_signals: List[Dict[str, Any]] = []
        self._recent_trades: List[Dict[str, Any]] = []
        self._max_recent: int = 500

        # market stats (24h high/low/volume/pct) — заполняется фидами best-effort
        self._market_stats: Dict[str, Dict[str, Any]] = {}
        self._market_stats_lock = threading.RLock()

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
            _log_throttled(
                "uiapi.binder_init",
                "warning",
                "UIAPI: StateBinder init failed; falling back to legacy snapshot path",
                interval_s=60.0,
                exc_info=True,
            )
            self._binder = None

        # STEP1.3.3: троттлинг для runtime-персистентности
        # (чтобы не писать state.json на каждый тик).
        self._last_runtime_persist_ts: float = 0.0

        # UI READ-ONLY: smart suppression for repetitive blocked actions (UI-only)
        # Goal: avoid spamming events.jsonl + Explain panel while preserving evidence.
        # Window can be tuned: MB_UI_RO_SUPPRESS_WINDOW_S (default 3.0)
        try:
            self._ui_ro_suppress_window_s: float = float(
                str(os.environ.get("MB_UI_RO_SUPPRESS_WINDOW_S", "3.0")).strip() or "3.0"
            )
        except Exception:
            self._ui_ro_suppress_window_s = 3.0

        # Per-action suppression state:
        # { action: {"last_emit_ts": float, "suppressed": int, "first_suppressed_ts": float|None, "last_suppressed_ts": float|None } }
        self._ui_ro_suppress: Dict[str, Dict[str, Any]] = {}

    def get_last_order_error(self) -> Optional[str]:
        """Последняя причина блокировки/ошибки ордера (для UI explain)."""
        return self._last_order_error

    # ==============================
    #        UI READ-ONLY GUARD
    # ==============================
    def is_ui_read_only(self) -> bool:
        return bool(getattr(self, "_ui_read_only", True))

    def set_ui_read_only(self, value: bool) -> None:
        self._ui_read_only = bool(value)

    def _guard_write(self, action: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """Central write-guard for UIAPI.

        If UI is read-only (default), any write action is blocked.
        Override: MB_UI_READ_ONLY=0

        Smart suppression:
          - first block emits UI_READ_ONLY_BLOCK immediately
          - repeated blocks of the same action within window are suppressed
          - next emitted block carries suppressed_count + timestamps
        """
        if not self.is_ui_read_only():
            return True

        now = time.time()

        # Normalize action via SSOT registry (never raises)
        act = normalize_ui_action(action)
        act_title = describe_ui_action(act)

        # best-effort: store last error for diagnostics
        try:
            self._last_order_error = f"UI read-only: '{act}' blocked"
        except Exception:
            pass

        # suppression state (best-effort)
        try:
            window_s = float(getattr(self, "_ui_ro_suppress_window_s", 3.0) or 3.0)
        except Exception:
            window_s = 3.0

        st_map = getattr(self, "_ui_ro_suppress", None)
        if not isinstance(st_map, dict):
            st_map = {}
            try:
                self._ui_ro_suppress = st_map  # type: ignore
            except Exception:
                pass

        rec = st_map.get(act)
        if not isinstance(rec, dict):
            rec = {"last_emit_ts": 0.0, "suppressed": 0, "first_suppressed_ts": None, "last_suppressed_ts": None}
            st_map[act] = rec

        last_emit = 0.0
        try:
            last_emit = float(rec.get("last_emit_ts") or 0.0)
        except Exception:
            last_emit = 0.0

        # If within suppression window: do not emit event; just count
        if (now - last_emit) < window_s:
            try:
                rec["suppressed"] = int(rec.get("suppressed") or 0) + 1
            except Exception:
                rec["suppressed"] = 1
            if rec.get("first_suppressed_ts") is None:
                rec["first_suppressed_ts"] = now
            rec["last_suppressed_ts"] = now

            _log_throttled(
                "uiapi.read_only.suppressed",
                "warning",
                f"UIAPI: suppressed repeated read-only block '{act}'",
                interval_s=30.0,
            )
            return False

        # Window passed -> emit event (carrying suppressed summary, if any), then reset counters
        suppressed_count = 0
        first_sup = None
        last_sup = None
        try:
            suppressed_count = int(rec.get("suppressed") or 0)
        except Exception:
            suppressed_count = 0
        first_sup = rec.get("first_suppressed_ts")
        last_sup = rec.get("last_suppressed_ts")

        _emit_event(
            "UI_READ_ONLY_BLOCK",
            {
                "action": str(act),
                "action_title": str(act_title),
                "original_action": str(action),
                "details": details or {},
                "mode": str(getattr(self, "_ui_mode", "-")),
                "suppressed_count": int(suppressed_count),
                "suppression_window_s": float(window_s),
                "first_suppressed_ts": first_sup,
                "last_suppressed_ts": last_sup,
            },
            actor="ui",
        )

        # update suppression record
        rec["last_emit_ts"] = now
        rec["suppressed"] = 0
        rec["first_suppressed_ts"] = None
        rec["last_suppressed_ts"] = None

        _log_throttled(
            "uiapi.read_only.block",
            "warning",
            f"UIAPI: blocked write action '{act}' (READ-ONLY)",
            interval_s=30.0,
        )
        return False

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
                _log_throttled(
                    "uiapi.set_mode.executor",
                    "warning",
                    f"UIAPI: executor.set_mode({mode}) failed (ignored)",
                    interval_s=60.0,
                    exc_info=True,
                )

        # и в TPSL (если реализовано)
        if self.tpsl is not None and hasattr(self.tpsl, "set_mode"):
            try:
                self.tpsl.set_mode(mode)
            except Exception:
                _log_throttled(
                    "uiapi.set_mode.tpsl",
                    "warning",
                    f"UIAPI: tpsl.set_mode({mode}) failed (ignored)",
                    interval_s=60.0,
                    exc_info=True,
                )
        _emit_event("MODE_SET", {"mode": self._ui_mode}, actor="ui")


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

    def get_trading_status(self) -> Dict[str, Any]:
        """
        STEP 2.0 — Status Surface (read-only):
        canonical /status-like payload for UI (FSM + policy), no side effects.
        """
        try:
            from core.autonomy_policy import AutonomyPolicyStore
            from core.trading_state_machine import TradingStateMachine
            from core.status_service import StatusService

            policy = AutonomyPolicyStore()
            fsm = TradingStateMachine()
            svc = StatusService(policy, fsm)
            return svc.build_status().to_dict()
        except Exception as e:
            return {"error": f"unavailable: {e!r}"}

    # ==============================
    #   TIME UTILS (STEP1.4.3)
    # ==============================
    def _normalize_ts(self, ts: Optional[float]) -> float:
        """
        Привести timestamp к секундам (float) на стороне UI.
        """
        if ts is None:
            import time as _time
            return _time.time()
        try:
            v = float(ts)
        except Exception:
            import time as _time
            return _time.time()

        if v >= 1e12:
            v = v / 1000.0

        if v <= 0:
            import time as _time
            return _time.time()

        return v
        
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
            _log_throttled(
                "uiapi.append_bounded",
                "debug",
                "UIAPI: append_bounded failed (ignored)",
                interval_s=60.0,
                exc_info=True,
            )

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

    def persist_signal_record(self, rec: dict) -> None:
        """
        Core-owned persistence for signals history.
        UI should NOT write runtime/signals.jsonl directly.

        NOTE:
        UIAPI must NOT do file I/O. Delegates to core.signal_store.
        """
        try:
            from core.signal_store import append_signal_record
            append_signal_record(rec)
        except Exception:
            # best-effort: never crash UI/core loop, but no silent fail
            # (log here is optional; if you already have project-wide logging, keep it minimal)
            try:
                import logging
                logging.getLogger(__name__).exception("UIAPI: persist_signal_record delegation failed")
            except Exception:
                # last resort: still avoid raising to UI
                return

    def persist_equity_point(self, snapshot: dict, source: str = "UI") -> None:
        """
        UI-safe: UI calls this, but the actual file I/O is done in tools/ipc_equity.py (runtime layer).
        """
        if not self._guard_write(
            "persist_equity_point",
            {
                "source": str(source),
                "mode": str(snapshot.get("mode") if isinstance(snapshot, dict) else "SIM"),
            },
        ):
            return

        if _append_equity_point is None:
            _log_throttled(
                "uiapi.equity_point.no_impl",
                "warning",
                "UIAPI: _append_equity_point not available (tools.ipc_equity missing?)",
                interval_s=30.0,
            )
            return

        try:
            ts = float(snapshot.get("ts")) if isinstance(snapshot, dict) else time.time()
        except Exception:
            ts = time.time()

        try:
            eq = float(snapshot.get("equity")) if isinstance(snapshot, dict) else 0.0
        except Exception:
            eq = 0.0

        try:
            mode = snapshot.get("mode") if isinstance(snapshot, dict) else "SIM"
        except Exception:
            mode = "SIM"

        _append_equity_point(ts=ts, equity=eq, mode=mode, source=source)

    def get_recent_signals_tail(self, limit: int = 500) -> list[dict]:
        """
        Prefer in-memory buffer; UI uses this for Signals window.
        """
        try:
            buf = getattr(self, "_recent_signals", None)
            if not buf:
                return []
            items = list(buf)
            if limit and len(items) > limit:
                items = items[-limit:]
            # return newest-first for UI convenience
            return list(reversed(items))
        except Exception:
            return []

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
    #   UI Runtime Isolation (HARD-1A)
    #   UI must NOT read/write runtime files directly
    # ==============================
    def _runtime_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent / "runtime"

    def _trade_journal_path(self) -> Path:
        return self._runtime_dir() / "trades.jsonl"

    def _ticks_stream_path(self) -> Path:
        return self._runtime_dir() / "ticks_stream.jsonl"

    def persist_trade_record(self, rec: dict) -> None:
        """Core-owned persistence for trades history (runtime/trades.jsonl)."""
        if not self._guard_write(
            "persist_trade_record",
            {"keys": sorted(list(rec.keys())) if isinstance(rec, dict) else []},
        ):
            return

        try:
            p = self._trade_journal_path()
            p.parent.mkdir(parents=True, exist_ok=True)

            line = json.dumps(rec, ensure_ascii=False)
            with p.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            log.exception("UIAPI: persist_trade_record failed")
            return

        # Also add to recent trades cache for UI
        try:
            row = {
                "ts": rec.get("ts") or rec.get("time") or rec.get("timestamp"),
                "symbol": rec.get("symbol"),
                "side": rec.get("side"),
                "qty": rec.get("qty") or rec.get("quantity"),
                "price": rec.get("price"),
                "pnl": rec.get("pnl"),
                "fee": rec.get("fee"),
                "source": rec.get("source") or rec.get("actor") or "ui",
                "exit": rec.get("price") or rec.get("exit"),
            }
            self.add_recent_trade(row)
        except Exception:
            log.exception("UIAPI: persist_trade_record -> add_recent_trade failed")

    def get_recent_trades_from_runtime(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Read last N trades from runtime/trades.jsonl (core-owned)."""
        try:
            p = self._trade_journal_path()
            if not p.exists():
                return []
            with p.open("r", encoding="utf-8") as f:
                lines = f.readlines()[-max(1, int(limit or 500)):]
        except Exception:
            log.exception("UIAPI: get_recent_trades_from_runtime read failed")
            return []

        rows: List[Dict[str, Any]] = []
        for ln in lines:
            try:
                rec = json.loads(ln)
            except Exception:
                continue

            ts_val = rec.get("ts")
            if isinstance(ts_val, (int, float)):
                try:
                    time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts_val))
                except Exception:
                    time_str = str(ts_val)
            else:
                time_str = str(ts_val or "")

            rows.append(
                {
                    "time": time_str,
                    "symbol": rec.get("symbol"),
                    "tier": "-",
                    "action": rec.get("side") or rec.get("status") or "",
                    "tp": None,
                    "sl": None,
                    "pnl_pct": rec.get("pnl_pct"),
                    "pnl_abs": rec.get("pnl_cash"),
                    "qty": rec.get("qty"),
                    "entry": rec.get("entry"),
                    "exit": rec.get("price") or rec.get("exit"),
                }
            )
        return rows

    def get_trades_for_range(
        self,
        symbol: str,
        ts_from_ms: int,
        ts_to_ms: int,
        *,
        limit: int = 5000,
    ) -> List[Dict[str, Any]]:
        """Read trades.jsonl tail and return raw trades filtered by time range.

        Returns a list of dicts (best-effort):
          {"ts_ms": int, "symbol": "BTCUSDT", "side": "BUY"|"SELL", "price": float, "qty": float|None}

        Notes:
        - core-owned runtime I/O (UI must not access filesystem directly)
        - missing file => []
        - invalid/partial rows are skipped
        """
        sym_u = (symbol or "").upper().strip()
        try:
            t0 = int(ts_from_ms or 0)
            t1 = int(ts_to_ms or 0)
        except Exception:
            return []
        if not sym_u or t0 <= 0 or t1 <= 0 or t1 <= t0:
            return []

        try:
            p = self._trade_journal_path()
            if not p.exists():
                return []
            with p.open("r", encoding="utf-8") as f:
                lines = f.readlines()
            if limit and len(lines) > int(limit):
                lines = lines[-int(limit) :]
        except Exception:
            log.exception("UIAPI: get_trades_for_range read failed")
            return []

        out: List[Dict[str, Any]] = []
        for ln in lines:
            ln = (ln or "").strip()
            if not ln:
                continue
            try:
                rec = json.loads(ln)
            except Exception:
                continue

            try:
                rs = (rec.get("symbol") or "").upper().strip()
                if rs != sym_u:
                    continue
            except Exception:
                continue

            try:
                ts_ms = rec.get("ts")
                if not isinstance(ts_ms, (int, float)):
                    continue
                ts_ms_i = int(ts_ms)
            except Exception:
                continue

            if ts_ms_i < t0 or ts_ms_i >= t1:
                continue

            side = str(rec.get("side") or rec.get("action") or "").upper().strip()
            if side not in ("BUY", "SELL"):
                # skip non-trade journal records
                continue

            price_raw = rec.get("price")
            if price_raw is None:
                price_raw = rec.get("entry")
            if price_raw is None:
                price_raw = rec.get("exit")
            try:
                price = float(price_raw)
            except Exception:
                continue
            if price <= 0:
                continue

            qty_val = rec.get("qty")
            try:
                qty = float(qty_val) if qty_val is not None else None
            except Exception:
                qty = None

            out.append(
                {
                    "ts_ms": ts_ms_i,
                    "symbol": sym_u,
                    "side": side,
                    "price": price,
                    "qty": qty,
                }
            )

        return out

    def get_tick_series(self, symbol: str, max_points: int = 300) -> tuple[list[int], list[float]]:
        """Return chart series from runtime/ticks_stream.jsonl (core-owned)."""
        sym_u = (symbol or "").upper()
        prices: list[float] = []
        times: list[int] = []

        try:
            p = self._ticks_stream_path()
            if not p.exists():
                return times, prices
            with p.open("r", encoding="utf-8") as f:
                lines = f.readlines()[-max(1, int(max_points or 300)):]
        except Exception:
            log.exception("UIAPI: get_tick_series read failed")
            return times, prices

        for ln in lines:
            try:
                obj = json.loads(ln)
            except Exception:
                continue
            if obj.get("symbol") and str(obj.get("symbol")).upper() != sym_u:
                continue
            price = obj.get("price") or obj.get("p") or obj.get("close")
            if price is None:
                continue
            try:
                prices.append(float(price))
                times.append(len(times))
            except Exception:
                continue

        return times, prices

    def get_ohlc_series(
        self,
        symbol: str,
        timeframe_s: int,
        *,
        max_candles: int = 300,
        max_ticks: int = 5000,
    ) -> dict:
        """Return OHLC candles built from runtime/ticks_stream.jsonl (core-owned, read-only).

        Fallback (read-only, in-memory only):
          - If ticks stream is missing/empty/unreadable, best-effort fetch Binance klines
            and return candles without writing anything to runtime.

        Contract (best-effort):
          {
            "symbol": "BTCUSDT",
            "timeframe_s": 60,
            "source": "runtime/ticks_stream.jsonl" | "binance/klines",
            "last_tick_ts_ms": 1700000000000 | null,
            "candles": [
              {"ts_open_ms": 1700000000000, "o": 1.0, "h": 1.1, "l": 0.9, "c": 1.05, "n": 42},
              ...
            ],
            "reason": "" | "NO_STREAM" | "NO_TICKS" | "BAD_TIMEFRAME" | "READ_FAILED" | "BOOTSTRAP" | "BOOTSTRAP_FAILED"
          }

        UI must treat this as *read-only observability*.
        """
        sym_u = (symbol or "").upper().strip()

        tf_raw = timeframe_s
        tf_s = int(timeframe_s or 0)

        # Some legacy paths may pass timeframe in minutes (1,5,15) instead of seconds.
        # IMPORTANT: 60 is a valid 1m value in seconds, so DO NOT auto-normalize 60 -> 3600.
        if tf_s in (1, 5, 15):
            tf_s = tf_s * 60

        # DEBUG to stdout (throttled) to confirm what TF actually arrives in live UI
        try:
            _dbg_last = getattr(self, "_dbg_last_ohlc_tf_log_ts", 0.0) or 0.0
        except Exception:
            _dbg_last = 0.0

        try:
            now_ts = time.time()
        except Exception:
            now_ts = 0.0

        if now_ts - _dbg_last >= 30.0:
            try:
                setattr(self, "_dbg_last_ohlc_tf_log_ts", now_ts)
            except Exception:
                pass
            print(f"UIAPI: DEBUG get_ohlc_series symbol={sym_u} tf_raw={tf_raw!r} -> tf_s={tf_s}")

        if not sym_u or tf_s <= 0:
            return {
                "symbol": sym_u,
                "timeframe_s": tf_s,
                "source": "runtime/ticks_stream.jsonl",
                "last_tick_ts_ms": None,
                "candles": [],
                "reason": "BAD_TIMEFRAME",
            }

        # Tick timeframe: bootstrap from klines is not applicable (ticks are stream-only)
        _tf_map = {
            60: "1m",
            300: "5m",
            900: "15m",
            3600: "1h",
        }

        def _bootstrap_from_klines(reason_if_ok: str = "BOOTSTRAP") -> Optional[dict]:
            """Best-effort Binance klines bootstrap.

            IMPORTANT (v2.3.11.6):
              - UI must never wait for HTTP.
              - We only return cached candles immediately.
              - If cache is empty/stale, we schedule background fetch and return BOOTSTRAP_PENDING.
              - Never writes to runtime; cache is process-local (in-memory).
            """
            interval = _tf_map.get(tf_s)
            if not interval:
                _log_throttled(
                    f"uiapi.bootstrap.bad_tf.{sym_u}",
                    "warning",
                    f"UIAPI: BOOTSTRAP skipped (unsupported tf_s={tf_s} for symbol={sym_u})",
                    interval_s=30.0,
                )
                return None

            # init cache on UIAPI instance (process-local)
            cache = getattr(self, "_ohlc_bootstrap_cache", None)
            if not isinstance(cache, dict):
                cache = {}
                try:
                    setattr(self, "_ohlc_bootstrap_cache", cache)
                except Exception:
                    pass

            lock = getattr(self, "_ohlc_bootstrap_lock", None)
            if not (hasattr(lock, "acquire") and hasattr(lock, "release")):
                lock = threading.RLock()
                try:
                    setattr(self, "_ohlc_bootstrap_lock", lock)
                except Exception:
                    pass

            inflight = getattr(self, "_ohlc_bootstrap_inflight", None)
            if not isinstance(inflight, dict):
                inflight = {}
                try:
                    setattr(self, "_ohlc_bootstrap_inflight", inflight)
                except Exception:
                    pass

            # TTL for cache
            try:
                ttl_s = float(str(os.environ.get("MB_UI_OHLC_BOOTSTRAP_CACHE_TTL_S", "15")).strip() or "15")
            except Exception:
                ttl_s = 15.0

            # Request throttle (avoid thread spam)
            try:
                req_min_gap_s = float(str(os.environ.get("MB_UI_OHLC_BOOTSTRAP_REQ_MIN_GAP_S", "2.0")).strip() or "2.0")
            except Exception:
                req_min_gap_s = 2.0

            limit = int(max(1, min(int(max_candles or 300), 500)))
            cache_key = f"{sym_u}|{tf_s}|{limit}"

            now = time.time()

            # 1) Serve from cache (fresh OR stale) to avoid flicker.
            #    If stale -> still return immediately, but also schedule a refresh in background.
            stale_payload = None
            try:
                with lock:
                    ent = cache.get(cache_key)
                    if isinstance(ent, dict) and isinstance(ent.get("candles"), list) and ent.get("candles"):
                        ts = float(ent.get("ts") or 0.0)
                        candles_cached = ent.get("candles") or []
                        last_tick_cached = ent.get("last_tick_ts_ms")

                        if (now - ts) <= ttl_s:
                            return {
                                "symbol": sym_u,
                                "timeframe_s": tf_s,
                                "source": "binance/klines",
                                "last_tick_ts_ms": last_tick_cached,
                                "candles": candles_cached,
                                "reason": reason_if_ok,
                            }

                        # stale cache — return it (prevents chart jumping), but refresh in background
                        stale_payload = {
                            "symbol": sym_u,
                            "timeframe_s": tf_s,
                            "source": "binance/klines",
                            "last_tick_ts_ms": last_tick_cached,
                            "candles": candles_cached,
                            "reason": "BOOTSTRAP_STALE",
                        }
            except Exception:
                stale_payload = None

            # 2) Cache miss or stale → schedule background fetch (non-blocking)
            # Optional blocking warm-start (opt-in).
            # Default behavior remains NON-BLOCKING (SSOT safety).
            # Enable via: MB_UI_OHLC_BOOTSTRAP_BLOCKING_MS=800 (example)
            try:
                block_ms = int(str(os.environ.get("MB_UI_OHLC_BOOTSTRAP_BLOCKING_MS", "0")).strip() or "0")
            except Exception:
                block_ms = 0
            if block_ms < 0:
                block_ms = 0

            if block_ms > 0 and stale_payload is None:
                try:
                    import urllib.request
                    import urllib.parse

                    params = {"symbol": sym_u, "interval": interval, "limit": str(limit)}
                    url = "https://api.binance.com/api/v3/klines?" + urllib.parse.urlencode(params)

                    req = urllib.request.Request(
                        url,
                        headers={
                            "User-Agent": "MontrixBot/2.3.11.8 (bootstrap warm-start)",
                            "Accept": "application/json",
                        },
                        method="GET",
                    )

                    timeout_s = min(7.0, max(0.2, float(block_ms) / 1000.0))
                    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                        raw = resp.read()

                    data = json.loads(raw.decode("utf-8", errors="replace"))
                    if isinstance(data, list) and data:
                        candles_out = []
                        last_ts_ms = None
                        for row in data:
                            try:
                                ts_open_ms = int(row[0])
                                candles_out.append({
                                    "ts_open_ms": ts_open_ms,
                                    "o": float(row[1]),
                                    "h": float(row[2]),
                                    "l": float(row[3]),
                                    "c": float(row[4]),
                                    "n": 0,
                                })
                                last_ts_ms = ts_open_ms
                            except Exception:
                                continue

                        if candles_out:
                            with lock:
                                cache[cache_key] = {
                                    "ts": time.time(),
                                    "last_tick_ts_ms": last_ts_ms,
                                    "candles": candles_out,
                                }

                            return {
                                "symbol": sym_u,
                                "timeframe_s": tf_s,
                                "source": "binance/klines",
                                "last_tick_ts_ms": last_ts_ms,
                                "candles": candles_out,
                                "reason": "BOOTSTRAP_BLOCKING",
                            }
                except Exception:
                    # If blocking warm-start fails, fall back to non-blocking behavior
                    pass
            def _schedule_fetch() -> None:
                try:
                    with lock:
                        st = inflight.get(cache_key) or {}
                        last_req = float(st.get("last_req_ts") or 0.0)
                        running = bool(st.get("running"))
                        if running:
                            return
                        if (now - last_req) < req_min_gap_s:
                            return
                        inflight[cache_key] = {"running": True, "last_req_ts": now}

                    def _worker() -> None:
                        try:
                            import urllib.request
                            import urllib.parse

                            params = {"symbol": sym_u, "interval": interval, "limit": str(limit)}
                            url = "https://api.binance.com/api/v3/klines?" + urllib.parse.urlencode(params)

                            req = urllib.request.Request(
                                url,
                                headers={
                                    "User-Agent": "MontrixBot/2.3.11.6 (read-only bootstrap)",
                                    "Accept": "application/json",
                                },
                                method="GET",
                            )

                            with urllib.request.urlopen(req, timeout=7.0) as resp:
                                raw = resp.read()

                            data = json.loads(raw.decode("utf-8", errors="replace"))
                            if not isinstance(data, list) or not data:
                                return

                            candles_out = []
                            last_ts_ms = None
                            for row in data:
                                try:
                                    ts_open_ms = int(row[0])
                                    candles_out.append({
                                        "ts_open_ms": ts_open_ms,
                                        "o": float(row[1]),
                                        "h": float(row[2]),
                                        "l": float(row[3]),
                                        "c": float(row[4]),
                                        "n": 0,
                                    })
                                    last_ts_ms = ts_open_ms
                                except Exception:
                                    continue

                            if not candles_out:
                                return

                            with lock:
                                cache[cache_key] = {
                                    "ts": time.time(),
                                    "last_tick_ts_ms": last_ts_ms,
                                    "candles": candles_out,
                                }

                            _log_throttled(
                                f"uiapi.bootstrap.{sym_u}.{tf_s}",
                                "info",
                                f"UIAPI: BOOTSTRAP klines fetched {len(candles_out)} candles for {sym_u} ({interval})",
                                interval_s=30.0,
                            )
                        except Exception:
                            _log_throttled(
                                f"uiapi.bootstrap_failed.{sym_u}.{tf_s}",
                                "warning",
                                f"UIAPI: BOOTSTRAP klines failed for {sym_u}",
                                interval_s=30.0,
                                exc_info=True,
                            )
                        finally:
                            with lock:
                                inflight[cache_key]["running"] = False

                    threading.Thread(
                        target=_worker,
                        name=f"uiapi_ohlc_bootstrap_{sym_u}_{tf_s}",
                        daemon=True,
                    ).start()
                except Exception:
                    return

            _schedule_fetch()

            # If we have stale cache, serve it to avoid flicker/jumps.
            if stale_payload is not None:
                return stale_payload

            # Otherwise return a non-blocking placeholder
            return {
                "symbol": sym_u,
                "timeframe_s": tf_s,
                "source": "binance/klines",
                "last_tick_ts_ms": None,
                "candles": [],
                "reason": "BOOTSTRAP_PENDING",
            }

        # 1) Try runtime ticks stream first (core-owned, read-only)
        # v2.3.11.7 — performance: tail-read only last N lines + cache by file stat
        def _tail_lines_utf8(path, *, max_lines: int, max_bytes: int = 2_000_000) -> list[str]:
            """Read last max_lines lines without loading full file (best-effort)."""
            try:
                max_lines = int(max_lines)
            except Exception:
                max_lines = 5000
            max_lines = max(1, max_lines)

            try:
                with path.open("rb") as f:
                    try:
                        f.seek(0, 2)
                        end = f.tell()
                    except Exception:
                        end = 0

                    if end <= 0:
                        return []

                    # read from the end in chunks
                    chunk = 65536
                    data = b""
                    pos = end
                    while pos > 0 and data.count(b"\n") <= max_lines and len(data) < int(max_bytes):
                        read_sz = chunk if pos >= chunk else pos
                        pos -= read_sz
                        try:
                            f.seek(pos)
                        except Exception:
                            break
                        try:
                            buf = f.read(read_sz)
                        except Exception:
                            break
                        data = buf + data

                    # keep only last N lines
                    lines_b = data.splitlines()[-max_lines:]
                    out = []
                    for b in lines_b:
                        try:
                            out.append(b.decode("utf-8", errors="replace"))
                        except Exception:
                            continue
                    return out
            except Exception:
                return []

        # Cache: if ticks stream file did not change → reuse last computed candles (avoid CPU/UI stalls)
        cache_key = (sym_u, int(tf_s), int(max_candles or 0), int(max_ticks or 0))
        try:
            _ticks_ohlc_cache = getattr(self, "_ticks_ohlc_cache", None)
            if not isinstance(_ticks_ohlc_cache, dict):
                _ticks_ohlc_cache = {}
                try:
                    setattr(self, "_ticks_ohlc_cache", _ticks_ohlc_cache)
                except Exception:
                    pass
        except Exception:
            _ticks_ohlc_cache = {}

        try:
            p = self._ticks_stream_path()
            if not p.exists():

                # 2) Fallback to klines
                boot = _bootstrap_from_klines("BOOTSTRAP")
                if boot is not None:
                    return boot
                return {
                    "symbol": sym_u,
                    "timeframe_s": tf_s,
                    "source": "runtime/ticks_stream.jsonl",
                    "last_tick_ts_ms": None,
                    "candles": [],
                    "reason": "NO_STREAM",
                }

            # Read tail (best-effort). We don't want to load the whole file.
            # v2.3.11.7: cache by file stat to avoid re-parsing when unchanged
            try:
                st = p.stat()
                st_key = (int(getattr(st, "st_size", 0) or 0), int(getattr(st, "st_mtime_ns", 0) or 0))
            except Exception:
                st_key = None

            try:
                ent = _ticks_ohlc_cache.get(cache_key) if isinstance(_ticks_ohlc_cache, dict) else None
            except Exception:
                ent = None

            # v2.3.11.7.1 — HARD cache-hit: if ticks file unchanged → return cached result (zero CPU)
            try:
                if st_key is not None and isinstance(ent, dict) and ent.get("st_key") == st_key:
                    cached = ent.get("result")
                    if isinstance(cached, dict):
                        return cached
            except Exception:
                pass

            # v2.3.11.7.2 — UI-throttle:
            # If UI asks too frequently, serve last cached result even if file changed.
            # This dramatically reduces CPU/IO and removes UI freezes.
            try:
                throttle_ms = int(os.environ.get("MB_UI_OHLC_THROTTLE_MS", "350") or "350")
            except Exception:
                throttle_ms = 350
            throttle_ms = max(0, throttle_ms)

            try:
                now_mono = time.monotonic()
            except Exception:
                now_mono = None

            try:
                if throttle_ms > 0 and now_mono is not None and isinstance(ent, dict):
                    last_served = ent.get("served_mono")
                    cached = ent.get("result")
                    if isinstance(last_served, (int, float)) and isinstance(cached, dict):
                        if (now_mono - float(last_served)) * 1000.0 < float(throttle_ms):
                            return cached
            except Exception:
                pass

            lines = _tail_lines_utf8(p, max_lines=int(max_ticks or 5000))

            # store raw tail cache info (computed later)
            _pending_st_key = st_key

        except Exception:
            log.exception("UIAPI: get_ohlc_series ticks_stream read failed")
            boot = _bootstrap_from_klines("BOOTSTRAP")
            if boot is not None:
                return boot
            return {
                "symbol": sym_u,
                "timeframe_s": tf_s,
                "source": "runtime/ticks_stream.jsonl",
                "last_tick_ts_ms": None,
                "candles": [],
                "reason": "READ_FAILED",
            }

        ticks: list[dict] = []
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                obj = json.loads(ln)
            except Exception:
                continue
            if obj.get("symbol") and str(obj.get("symbol")).upper() != sym_u:
                continue
            ticks.append(obj)

        if not ticks:
            boot = _bootstrap_from_klines("BOOTSTRAP")
            if boot is not None:
                return boot
            return {
                "symbol": sym_u,
                "timeframe_s": tf_s,
                "source": "runtime/ticks_stream.jsonl",
                "last_tick_ts_ms": None,
                "candles": [],
                "reason": "NO_TICKS",
            }

        try:
            candles, last_ts = build_ohlc_from_ticks(
                ticks,
                timeframe_ms=tf_s * 1000,
                max_candles=max_candles,
            )
            if not candles:
                boot = _bootstrap_from_klines("BOOTSTRAP")
                if boot is not None:
                    return boot

            # Anti-flicker (working, not dead code):
            # If tick stream is present but not warmed up, prefer bootstrap to avoid flashing.
            try:
                min_warm = int(os.environ.get("MB_UI_OHLC_MIN_WARM_CANDLES", "10") or "10")
            except Exception:
                min_warm = 10
            min_warm = max(0, int(min_warm or 0))

            if min_warm > 0 and isinstance(candles, list) and len(candles) < min_warm:
                boot = _bootstrap_from_klines("BOOTSTRAP_PREFERRED")
                if boot is not None and isinstance(boot.get("candles"), list) and len(boot["candles"]) >= len(candles):
                    return boot

            result = {
                "symbol": sym_u,
                "timeframe_s": tf_s,
                "source": "runtime/ticks_stream.jsonl",
                "last_tick_ts_ms": last_ts,
                "candles": candles,
                "reason": "",
            }

            # store computed result into cache by file stat (if available)
            try:
                if isinstance(_ticks_ohlc_cache, dict):
                    st_key2 = None
                    try:
                        st_key2 = _pending_st_key
                    except Exception:
                        st_key2 = None

                    try:
                        served_mono = time.monotonic()
                    except Exception:
                        served_mono = None

                    if st_key2 is not None:
                        _ticks_ohlc_cache[cache_key] = {
                            "st_key": st_key2,
                            "result": result,
                            "served_mono": served_mono,
                        }
            except Exception:
                pass

            return result

            if len(candles) < min_warm:
                boot = _bootstrap_from_klines("BOOTSTRAP_PREFERRED")
                if boot is not None and isinstance(boot.get("candles"), list) and len(boot["candles"]) >= len(candles):
                    return boot

            return {
                "symbol": sym_u,
                "timeframe_s": tf_s,
                "source": "runtime/ticks_stream.jsonl",
                "last_tick_ts_ms": last_ts,
                "candles": [c.as_dict() for c in candles],
                "reason": "",
            }
        except Exception:
            log.exception("UIAPI: get_ohlc_series build failed")
            boot = _bootstrap_from_klines("BOOTSTRAP")
            if boot is not None:
                return boot
            return {
                "symbol": sym_u,
                "timeframe_s": tf_s,
                "source": "runtime/ticks_stream.jsonl",
                "last_tick_ts_ms": None,
                "candles": [],
                "reason": "BUILD_FAILED",
            }

    def open_trades_journal_file(self) -> None:
        """Open runtime/trades.jsonl in OS (UI does not see paths)."""
        try:
            p = self._trade_journal_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists():
                p.write_text("", encoding="utf-8")
            if os.name == "nt":
                os.startfile(str(p))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
        except Exception:
            log.exception("UIAPI: open_trades_journal_file failed")

    def open_runtime_folder(self) -> None:
        """Open runtime folder in OS (UI does not see paths)."""
        try:
            p = self._runtime_dir()
            p.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(str(p))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
        except Exception:
            log.exception("UIAPI: open_runtime_folder failed")

    def update_market_stats(self, symbol: str, stats: Dict[str, Any]) -> None:
        """Обновить market stats по символу (best-effort). Вызывается фидами из их потока."""
        if not symbol:
            return
        if not isinstance(stats, dict):
            return
        sym = str(symbol).upper()
        try:
            with self._market_stats_lock:
                cur = self._market_stats.get(sym) or {}
                cur.update(stats)
                cur["ts"] = int(time.time() * 1000)
                self._market_stats[sym] = cur
        except Exception:
            _log_throttled(
                "uiapi.market_stats.update",
                "debug",
                f"UIAPI: update_market_stats failed for {sym} (ignored)",
                interval_s=60.0,
                exc_info=True,
            )
            return

    def get_market_stats(self) -> Dict[str, Dict[str, Any]]:
        """Снапшот market_stats (копия), безопасно для UI."""
        try:
            with self._market_stats_lock:
                return dict(self._market_stats)
        except Exception:
            return {}

    # ==============================
    #      СНАПШОТ СОСТОЯНИЯ
    # ==============================
    def _fallback_positions_from_runtime(self, runtime_state: dict, realm: str) -> dict:
        """
        realm: "real" | "sim"
        Пытается достать positions из runtime_state (state.json/sim_state.json),
        чтобы UI не зависел от TPSL при SAFE/PANIC/autoloop OFF.
        """
        if not isinstance(runtime_state, dict):
            return {}

        bucket = runtime_state.get(realm) or runtime_state.get(realm.upper()) or {}
        if not isinstance(bucket, dict):
            return {}

        pos = bucket.get("positions") or bucket.get("open_positions") or bucket.get("positions_map") or {}
        if isinstance(pos, list):
            out = {}
            for p in pos:
                if isinstance(p, dict) and p.get("symbol"):
                    out[str(p["symbol"]).upper()] = p
            return out

        if isinstance(pos, dict):
            # нормализуем ключи в UPPER
            out = {}
            for k, v in pos.items():
                out[str(k).upper()] = v
            return out

        return {}
    
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

        # STEP1.4.2: core delay detector flags from StateEngine.snapshot()
        core_lag_s: Optional[float] = None
        core_stall: Optional[bool] = None

        # STEP1.4.3: time integrity flags from StateEngine.snapshot()
        core_time_backwards: Optional[bool] = None
        core_time_backwards_delta_s: Optional[float] = None
        try:
            v = core_snap.get("core_time_backwards")
            core_time_backwards = bool(v) if v is not None else None
        except Exception:
            core_time_backwards = None
        try:
            v = core_snap.get("core_time_backwards_delta_s")
            core_time_backwards_delta_s = float(v) if v is not None else None
        except Exception:
            core_time_backwards_delta_s = None
        try:
            v = core_snap.get("core_lag_s")
            core_lag_s = float(v) if v is not None else None
        except Exception:
            core_lag_s = None
        try:
            v = core_snap.get("core_stall")
            core_stall = bool(v) if v is not None else None
        except Exception:
            core_stall = None

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

        # equity из TPSL (НЕ зависит от fallback)
        if self.tpsl is not None:
            try:
                equity = float(getattr(self.tpsl, "equity"))
            except Exception:
                equity = None

        # fallback (REAL): позиции из runtime_state, если TPSL недоступен / SAFE / autoloop OFF
        if not positions and str(self._ui_mode).upper() == "REAL":
            try:
                rt = load_runtime_state()
                positions = self._fallback_positions_from_runtime(rt, realm="real")
            except Exception:
                positions = {}

        # fallback: equity можно попытаться взять из core_snap
        if equity is None:
            try:
                eq_raw = core_snap.get("equity")
                if eq_raw is not None:
                    equity = float(eq_raw)
            except Exception:
                equity = None

        # fallback (SIM): equity + portfolio из runtime_state["sim"] (sim_state.json)
        sim_portfolio: Optional[Dict[str, Any]] = None
        if str(self._ui_mode).upper() == "SIM":
            try:
                rt = load_runtime_state()
                sim = rt.get("sim") if isinstance(rt, dict) else None
                if isinstance(sim, dict):
                    # equity
                    eq_raw = sim.get("equity")
                    if eq_raw is None:
                        pf = sim.get("portfolio")
                        if isinstance(pf, dict):
                            eq_raw = pf.get("equity")
                    if equity is None and eq_raw is not None:
                        equity = float(eq_raw)

                    # portfolio (для pnl / open fallbacks)
                    pf = sim.get("portfolio")
                    if isinstance(pf, dict):
                        sim_portfolio = pf
            except Exception:
                sim_portfolio = None

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

        # fallback (SIM): pnl_% из sim_state.json
        if str(self._ui_mode).upper() == "SIM" and sim_portfolio is not None:
            if pnl_day_pct is None:
                pnl_day_pct = _safe_float(sim_portfolio.get("pnl_day_pct"))
            if pnl_total_pct is None:
                pnl_total_pct = _safe_float(sim_portfolio.get("pnl_total_pct"))

        try:
            open_positions_count = len(positions)
        except Exception:
            open_positions_count = 0
        # fallback (SIM): open_positions_count из sim_state.json
        if str(self._ui_mode).upper() == "SIM" and sim_portfolio is not None:
            if not open_positions_count:
                try:
                    v = sim_portfolio.get("open_positions_count")
                    if v is not None:
                        open_positions_count = int(v)
                except Exception:
                    _log_throttled(
                        "uiapi.sim.open_positions_count",
                        "debug",
                        "UIAPI: SIM open_positions_count fallback failed (ignored)",
                        interval_s=60.0,
                        exc_info=True,
                    )

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

        portfolio: Dict[str, Any] = {
            "equity": equity,
            "pnl_day_pct": pnl_day_pct,
            "pnl_total_pct": pnl_total_pct,
            "open_positions_count": open_positions_count,
            "open_pnl_abs": open_pnl_abs,
            "open_pnl_pct": open_pnl_pct,
        }

        # --- 5) Health-блок ---
        health: Dict[str, Any] = {
            "status": "OK",
            "messages": [],
        }

        # STEP1.4.2: core stall indicator (no actions here)
        if core_lag_s is not None:
            try:
                health["core_lag_s"] = core_lag_s
            except Exception:
                _log_throttled(
                    "uiapi.health.core_lag_s",
                    "debug",
                    "UIAPI: health['core_lag_s'] assign failed (ignored)",
                    interval_s=60.0,
                    exc_info=True,
                )
        if core_stall is not None:
            try:
                health["core_stall"] = core_stall
                if core_stall:
                    health["status"] = "WARN"
                    try:
                        msgs = health.get("messages")
                        if not isinstance(msgs, list):
                            msgs = []
                            health["messages"] = msgs
                        msgs.append("CORE_STALL")
                    except Exception:
                        _log_throttled(
                            "uiapi.health.core_stall_msgs",
                            "debug",
                            "UIAPI: health messages append failed (ignored)",
                            interval_s=60.0,
                            exc_info=True,
                        )
            except Exception:
                _log_throttled(
                    "uiapi.health.core_stall",
                    "debug",
                    "UIAPI: core_stall propagation failed (ignored)",
                    interval_s=60.0,
                    exc_info=True,
                )

        core_health = core_snap.get("health")
        if isinstance(core_health, dict):
            try:
                for k, v in core_health.items():
                    health[k] = v
            except Exception:
                _log_throttled(
                    "uiapi.health.merge",
                    "debug",
                    "UIAPI: health merge failed (ignored)",
                    interval_s=60.0,
                    exc_info=True,
                )

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
            "core_lag_s": core_lag_s,
            "core_stall": core_stall,       
            "core_time_backwards": core_time_backwards,
            "core_time_backwards_delta_s": core_time_backwards_delta_s,            
            "safe_mode": core_snap.get("safe_mode") or {},
            "heartbeats": hb.snapshot(),
            "market_stats": self.get_market_stats(),
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

    def is_panic_active(self) -> bool:
        """
        UI-safe: проверка состояния PANIC.

        Возвращает:
        - True, если runtime сообщает активный PANIC;
        - False в остальных случаях (best-effort).

        UI не взаимодействует с runtime напрямую.
        """
        try:
            from core.panic_facade import is_panic_active  # core-owned facade
            return bool(is_panic_active())
        except Exception:
            return False

    def persist_sim_state(self, snapshot: Dict[str, Any]) -> None:
        """UI-safe: сохранить sim_state (UI не импортирует runtime.sim_state_tools)."""
        if not self._guard_write("persist_sim_state"):
            return
        if not isinstance(snapshot, dict):
            return
        try:
            # локальный импорт, чтобы не раздувать зависимости при старте
            from runtime.sim_state_tools import save_sim_state
            save_sim_state(snapshot)
        except Exception:
            _log_throttled(
                "uiapi.persist_sim_state",
                "warning",
                "UIAPI: persist_sim_state failed (ignored)",
                interval_s=60.0,
                exc_info=True,
            )

    def maybe_persist_runtime_state(self, snapshot: Optional[Dict[str, Any]] = None) -> None:
        """
        STEP1.3.3 — best-effort runtime-персистентность.

        Вызывается из UI (SnapshotService) не чаще, чем раз в N секунд.
        Обновляет runtime_state на основе UI-снапшота (positions + meta),
        не затрагивая sim-часть.
        """
        if not self._guard_write("maybe_persist_runtime_state"):
            return
        # Лёгкий time-based throttle, чтобы не заливать диск.
        try:
            now = time.time()
            last = float(getattr(self, "_last_runtime_persist_ts", 0.0))
            # не чаще раза в 5 секунд
            if now - last < 5.0:
                return
        except Exception:
            _log_throttled(
                "uiapi.persist_runtime.throttle",
                "debug",
                "UIAPI: runtime persist throttle check failed (ignored)",
                interval_s=60.0,
                exc_info=True,
            )

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
            _log_throttled(
                "uiapi.persist_runtime.write",
                "warning",
                "UIAPI: persist_from_ui_snapshot failed (ignored)",
                interval_s=60.0,
                exc_info=True,
            )

    def reset_sim_state(self) -> None:
        """
        Запрос от UI на полный сброс SIM-состояния.

        UI не трогает файлы напрямую: всё идёт через core.runtime_state.reset_sim_state().
        """
        if not self._guard_write("reset_sim_state"):
            return
        try:
            reset_sim_state()
        except Exception:
            _log_throttled(
                "uiapi.reset_sim_state",
                "warning",
                "UIAPI: reset_sim_state failed (ignored)",
                interval_s=60.0,
                exc_info=True,
            )

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
            _log_throttled(
                "uiapi.snapshot.binder",
                "warning",
                "UIAPI: StateBinder snapshot path failed; falling back",
                interval_s=60.0,
                exc_info=True,
            )

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
            ts_n = self._normalize_ts(ts)
            state.upsert_ticker(symbol_u, price, ts=ts_n)
        except Exception:
            return 0

        return 1

    def on_tick(
        self,
        symbol: str,
        price: float,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
        ts: Optional[float] = None,
        write_stream: bool = True,
    ) -> int:
        """
        UI → ядро: проброс тика (price + bid/ask) в StateEngine.

        write_stream=False используется для ingest из runtime/ticks_stream.jsonl,
        чтобы не было эха (upsert_ticker по умолчанию пишет обратно в stream).
        """
        state = self.state
        if not hasattr(state, "upsert_ticker"):
            return 0

        try:
            symbol_u = str(symbol or "").upper()
        except Exception:
            symbol_u = "UNKNOWN"

        try:
            ts_n = self._normalize_ts(ts)
            state.upsert_ticker(
                symbol_u,
                float(price),
                bid=float(bid) if bid is not None else None,
                ask=float(ask) if ask is not None else None,
                ts=ts_n,
                write_stream=bool(write_stream),
            )
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

            v2.2.52:
            - Advisor snapshot remains UI-facing
            - First simple SIM strategy may emit rare SIM_DECISION_JOURNAL (events-only)
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

            # v2.2.52 — First Simple Strategy (SIM-only, events-only)
            try:
                from core.strategies.simple_strategy_v1 import (
                    maybe_publish_sim_decision_journal,
                    _DecisionMem,
                )

                mem = getattr(self, "_sim_strategy_mem_by_symbol", None)
                if mem is None or not isinstance(mem, dict):
                    mem = {}  # symbol -> _DecisionMem
                    self._sim_strategy_mem_by_symbol = mem  # type: ignore[attr-defined]

                # type: ignore[arg-type]
                maybe_publish_sim_decision_journal(mem, signal, recommendation, meta)
            except Exception:
                # strategy must never break UI flow
                pass

            # v2.2.104 — proposal rename: avoid clash with REAL Triple Strategy
            try:
                from core.strategies.proposal_2a1r import compute_proposal

                proposal = compute_proposal(signal, recommendation, meta)
                if isinstance(proposal, dict):
                    # attach into advisor snapshot (read-only surface)
                    try:
                        snap = dict(self._advisor_snapshot or {})
                    except Exception:
                        snap = {}
                    snap["sim_proposal_2a1r"] = proposal
                    self._advisor_snapshot = snap
            except Exception:
                # must never break UI flow
                pass

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

    def decide_replace_from_signal_and_reco(
        self,
        signal: Dict[str, Any],
        recommendation: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        """
        UI helper: получить ReplaceLogic decision для label/UX.

        Важно: это НЕ торговое решение и НЕ инициирует исполнение.
        """
        try:
            from core.replace_logic import decide_from_signal_and_reco

            return decide_from_signal_and_reco(signal, recommendation)
        except Exception:
            _log_throttled(
                "uiapi.replace_logic.decide",
                "warning",
                "UIAPI: ReplaceLogic decision failed (ignored)",
                interval_s=60.0,
                exc_info=True,
            )
            return None

    def update_tpsl_settings_from_ui(self, settings: Dict[str, Any]) -> None:
        """
        Обновить TPSL-настройки по запросу UI.
        """
        if not self._guard_write("update_tpsl_settings_from_ui"):
            return
        try:
            update_tpsl_settings(settings)
        except Exception:
            _log_throttled(
                "uiapi.tpsl_settings.update",
                "warning",
                "UIAPI: update_tpsl_settings_from_ui failed (ignored)",
                interval_s=60.0,
                exc_info=True,
            )

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
        safe_code: Optional[str] = None,
    ) -> bool:
        """
        Отправка рыночного ордера через executor.
        """
        # Используем основной вход executor.place_order, он уже делает DRY-run и логирует
        cid = None
        try:
            cid = new_cid() if new_cid is not None else None
        except Exception:
            cid = None

        _emit_event(
            "ORDER_REQUEST",
            {
                "action": "MARKET",
                "symbol": str(symbol).upper(),
                "qty": float(qty),
                "side": str(side or "BUY").upper(),
                "reason": str(reason or "UI"),
                "mode": str(self._ui_mode),
            },
            cid=cid,
        )

        # сброс последней ошибки ордера (для UI explain)
        self._last_order_error = None

        # --- EXECUTE ORDER (SIM/REAL depends on executor mode) ---
        try:
            self.executor.place_order(
                symbol=symbol,
                side=side,
                qty=qty,
                type_="MARKET",
                safe_code=safe_code,
            )
        except PermissionError as e:
            self._last_order_error = str(e)
            _log_throttled(
                "uiapi.buy_market.permission_error",
                "warning",
                f"UIAPI: ORDER_BLOCKED PermissionError: {self._last_order_error}",
                interval_s=10.0,
                exc_info=False,
            )
            _emit_event(
                "ORDER_BLOCKED",
                {
                    "action": "MARKET",
                    "symbol": str(symbol).upper(),
                    "qty": float(qty),
                    "side": str(side or "BUY").upper(),
                    "reason": "POLICY",
                    "error": self._last_order_error,
                    "mode": str(self._ui_mode),
                },
                cid=cid,
            )
            return False
        except Exception as e:
            self._last_order_error = repr(e)
            _emit_event(
                "ORDER_FAIL",
                {
                    "action": "MARKET",
                    "symbol": str(symbol).upper(),
                    "qty": float(qty),
                    "side": str(side or "BUY").upper(),
                    "error": repr(e),
                    "mode": str(self._ui_mode),
                },
                cid=cid,
            )
            return False
        
        _emit_event(
            "ORDER_OK",
            {
                "action": "MARKET",
                "symbol": str(symbol).upper(),
                "qty": float(qty),
                "side": str(side or "BUY").upper(),
                "mode": str(self._ui_mode),
            },
            cid=cid,
        )

        # TPSL-обёртка (если есть)
        if self.tpsl is not None and tpsl_cfg is not None:
            try:
                self.tpsl.attach(symbol, tpsl_cfg)
            except Exception:
                _log_throttled(
                    "uiapi.tpsl.attach",
                    "warning",
                    f"UIAPI: tpsl.attach({symbol}) failed (ignored)",
                    interval_s=30.0,
                    exc_info=True,
                )

        return True


    # ==============================
    #     ЗАКРЫТИЕ ПОЗИЦИЙ / PANIC
    # ==============================
    def close_position(self, symbol: str, reason: str = "UI_close") -> None:
        """
        Ручное закрытие позиции из UI (через TPSL).
        """
        if not self._guard_write(
            "close_position",
            {"symbol": str(symbol).upper(), "reason": str(reason or "UI_close"), "mode": str(self._ui_mode)},
        ):
            return

        _emit_event(
            "CLOSE_REQUEST",
            {"symbol": str(symbol).upper(), "reason": str(reason or "UI_close"), "mode": str(self._ui_mode)},
            actor="ui",
        )
        if self.tpsl is not None:
            try:
                self.tpsl.close(symbol.upper(), reason)
                _emit_event(
                    "CLOSE_OK",
                    {"symbol": str(symbol).upper(), "reason": str(reason or "UI_close"), "mode": str(self._ui_mode)},
                    actor="ui",
                )
            except Exception:
                log.exception("UIAPI: close_position failed")
                _emit_event(
                    "CLOSE_ERR",
                    {"symbol": str(symbol).upper(), "reason": str(reason or "UI_close"), "mode": str(self._ui_mode)},
                    actor="ui",
                )

    def panic(self, symbol: str) -> None:
        """
        Паник-селл из UI.
        """
        if not self._guard_write(
            "panic",
            {"symbol": str(symbol).upper(), "mode": str(self._ui_mode)},
        ):
            return

        _emit_event(
            "PANIC_REQUEST",
            {"symbol": str(symbol).upper(), "mode": str(self._ui_mode)},
            actor="ui",
        )
        if self.tpsl is not None:
            try:
                self.tpsl.panic(symbol.upper(), reason="UI_panic")
                _emit_event(
                    "PANIC_OK",
                    {"symbol": str(symbol).upper(), "mode": str(self._ui_mode)},
                    actor="ui",
                )
            except Exception:
                log.exception("UIAPI: panic failed")
                _emit_event(
                    "PANIC_ERR",
                    {"symbol": str(symbol).upper(), "mode": str(self._ui_mode)},
                    actor="ui",
                )

    def activate_panic_kill(self) -> None:
        if not self._guard_write(
            "activate_panic_kill",
            {"mode": str(self._ui_mode)},
        ):
            return

        _emit_event("PANIC_KILL_REQUEST", {"mode": str(self._ui_mode)}, actor="ui")
        try:
            if self.tpsl is not None:
                self.tpsl.activate_panic_kill(reason="UI_panic_kill")
            _emit_event("PANIC_KILL_OK", {"mode": str(self._ui_mode)}, actor="ui")
        except Exception:
            log.exception("UIAPI: activate_panic_kill failed")
            _emit_event("PANIC_KILL_ERR", {"mode": str(self._ui_mode)}, actor="ui")

    # ==============================
    #     REAL: MARKET ORDERS (DIAG ONLY; UI READ-ONLY GUARD)
    # ==============================
    def real_buy_market(self, symbol: str, quantity: float):
        if not self._guard_write(
            "real_buy_market",
            {"symbol": str(symbol).upper(), "quantity": float(quantity), "mode": str(self._ui_mode)},
        ):
            return None

        from core.orders_real import place_order_real
        return place_order_real(
            symbol=symbol,
            side="BUY",
            type_="MARKET",
            quantity=quantity,
            safe_code=None,
        )

    def real_sell_market(self, symbol: str, quantity: float):
        if not self._guard_write(
            "real_sell_market",
            {"symbol": str(symbol).upper(), "quantity": float(quantity), "mode": str(self._ui_mode)},
        ):
            return None

        from core.orders_real import place_order_real
        return place_order_real(
            symbol=symbol,
            side="SELL",
            type_="MARKET",
            quantity=quantity,
            safe_code=None,
        )


def build_ui_bridge(executor_mode: str = "SIM", enable_tpsl: bool = True) -> UIAPI:
    """Construct a UIAPI instance for UI-side SIM bridge without UI importing core primitives.

    IMPORTANT:
    - UI must not import/construct StateEngine/OrderExecutor/TPSL directly.
    - This helper keeps construction inside core layer (UIAPI module).
    """
    state = StateEngine(enable_tpsl=bool(enable_tpsl))
    executor = OrderExecutor(mode=str(executor_mode), state=state)

    tpsl: Optional[TPSLManager] = None
    if enable_tpsl:
        cfg = TPSSLConfig()
        tpsl = TPSLManager(executor, cfg)
        try:
            state.attach_tpsl(tpsl)
        except Exception:
            _log_throttled(
                "uiapi.build_ui_bridge.attach_tpsl",
                "warning",
                "UIAPI: build_ui_bridge: state.attach_tpsl(tpsl) failed; continuing without TPSL",
                interval_s=60.0,
                exc_info=True,
            )
            # TPSL wiring must not break UI bridge construction
            tpsl = None

    api = UIAPI(state, executor, tpsl=tpsl)
    return api
