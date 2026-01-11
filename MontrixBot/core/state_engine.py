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
from core.safe_mode import SafeModeManager
from core.health_api import get_health_snapshot_for_core

import logging

log = logging.getLogger(__name__)
_LOG_THROTTLE: Dict[str, float] = {}

def _log_throttled(key: str, level: str, msg: str, *, interval_s: float = 60.0, exc_info: bool = False) -> None:
    try:
        now = time.time()
        last = float(_LOG_THROTTLE.get(key, 0.0) or 0.0)
        if (now - last) < float(interval_s):
            return
        _LOG_THROTTLE[key] = now
        fn = getattr(log, level, log.warning)
        fn(msg, exc_info=exc_info)
    except Exception:
        # logging must never break core
        return

# ------ optional hooks: ipc_ticks ------

try:  # best-effort: UI-график через локальный JSONL
    from tools.ipc_ticks import append_tick as _append_tick  # type: ignore
except Exception:  # pragma: no cover
    def _append_tick(*args, **kwargs) -> None:  # type: ignore[override]
        return None

# ------ optional hooks: SAFE hard-lock (file based) ------

try:  # best-effort: если safe_lock доступен — при SAFE_MODE ставим hard lock файлом
    from tools.safe_lock import is_safe_on as _is_safe_on  # type: ignore
    from tools.safe_lock import enable_safe as _enable_safe_lock  # type: ignore
except Exception:  # pragma: no cover
    _is_safe_on = None  # type: ignore[assignment]
    _enable_safe_lock = None  # type: ignore[assignment]

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

        # STEP1.4.2: core heartbeat (timestamp of last successful core tick)
        self._last_core_tick_ts: float = time.time()
        self._core_stall_threshold_s: float = 2.0

        # STEP1.4.9A: SAFE-start guard (do not enter sticky SAFE before first real tick)
        self._boot_ts: float = time.time()
        self._has_seen_tick: bool = False

        # Grace window: allow UI to boot + feeds to connect without forcing sticky SAFE.
        # If no tick arrives after this window, SAFE may activate normally (stall/lag).
        self._safe_startup_grace_s: float = 10.0

        # журнал сделок для UI (используется UIAPI/Executor)
        self.tradebook: TradeBook = TradeBook()

        # TPSL-хук (может быть None, если TPSL не используется)
        self.tpsl: Optional[TPSLManager] = None  # type: ignore[assignment]
        self._enable_tpsl: bool = bool(enable_tpsl)

        # STEP1.4.3: time integrity
        self._core_time_backwards: bool = False
        self._core_time_backwards_delta_s: float = 0.0
        self._core_time_backwards_count: int = 0

        # STEP1.4.4: SafeMode policy/state (behavior, not just flags)
        self.safe_mode: SafeModeManager = SafeModeManager()

        # SAFE hard-lock edge-trigger (создаём файл SAFE_MODE один раз при входе в SAFE)
        self._safe_prev_active: bool = False
        self._safe_hard_lock_ok: bool = False
        self._safe_hard_lock_error: str = ""

        # STEP1.4.5+: "живой" статус safe_lock (проверяем каждый snapshot best-effort)
        self._safe_lock_on: bool | None = None
        self._safe_lock_error: str = ""

    # ----------------- TIME INTEGRITY -----------------

    def _normalize_ts(self, ts: Optional[float]) -> float:
        """
        Привести timestamp к секундам (float).

        Поддержка:
        - None -> time.time()
        - миллисекунды (>= 1e12) -> /1000
        - мусор/ошибки -> time.time()
        """
        if ts is None:
            return time.time()
        try:
            v = float(ts)
        except Exception:
            return time.time()

        # ms -> s (пример: 1765631277687)
        if v >= 1e12:
            v = v / 1000.0

        # отрицательные/нулевые считаем мусором
        if v <= 0:
            return time.time()

        return v

    def _check_time_integrity(self, ts_s: float) -> None:
        """
        Детект времени "назад" по сравнению с предыдущим core tick.
        """
        try:
            last = float(getattr(self, "_last_core_tick_ts", 0.0) or 0.0)
        except Exception:
            last = 0.0

        # допускаем микродребезг, но не "секунды назад"
        if last > 0.0 and ts_s + 1e-6 < (last - 0.25):
            self._core_time_backwards = True
            self._core_time_backwards_count = int(getattr(self, "_core_time_backwards_count", 0) or 0) + 1
            self._core_time_backwards_delta_s = float(last - ts_s)

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
            core_lag_s = float(self.get_core_lag_s())
            core_stall = bool(self.detect_stall())

            # STEP1.4.9A: SAFE-start guard
            # Before the first tick, core_lag/core_stall are not actionable (feeds may not be connected yet).
            try:
                if not bool(getattr(self, "_has_seen_tick", False)):
                    boot_ts = float(getattr(self, "_boot_ts", 0.0) or 0.0)
                    grace_s = float(getattr(self, "_safe_startup_grace_s", 0.0) or 0.0)
                    if boot_ts > 0.0 and grace_s > 0.0:
                        if (time.time() - boot_ts) <= grace_s:
                            core_lag_s = 0.0
                            core_stall = False
            except Exception:
                _log_throttled(
                    "snapshot.safe_start_guard",
                    "warning",
                    "snapshot: SAFE-start guard failed (ignored to keep snapshot alive)",
                    interval_s=60.0,
                    exc_info=True,
                )

            core_time_backwards = bool(getattr(self, "_core_time_backwards", False))
            core_time_backwards_delta_s = float(getattr(self, "_core_time_backwards_delta_s", 0.0) or 0.0)
            core_time_backwards_count = int(getattr(self, "_core_time_backwards_count", 0) or 0)

            # STEP1.4.4+: pre-check SAFE_LOCK (file SAFE_MODE) to feed SafeModeManager
            safe_lock_on_pre = False
            try:
                if _is_safe_on is not None:
                    safe_lock_on_pre = bool(_is_safe_on())
            except Exception:
                safe_lock_on_pre = False

            # STEP1.4.4: SafeMode policy/state is derived from core signals
            self.safe_mode.evaluate(
                {
                    "core_lag_s": core_lag_s,
                    "core_stall": core_stall,
                    "core_time_backwards": core_time_backwards,
                    "core_time_backwards_delta_s": core_time_backwards_delta_s,
                    "core_time_backwards_count": core_time_backwards_count,
                    "safe_lock_on": safe_lock_on_pre,
                }
            )

            # STEP1.4.4+: SAFE hard-lock (file SAFE_MODE in project root)
            # Важно: SAFE в core уже sticky (не выключаем автоматически).
            # Здесь только "поджимаем" REAL торговлю дополнительным file-lock'ом.
            sm = self.safe_mode.public_snapshot()
            cur_active = bool(sm.get("active", False))

            # STEP1.4.4+: explicit SAFE_MODE policy flag for all consumers
            safe_mode_active = cur_active

            prev_active = bool(getattr(self, "_safe_prev_active", False))
            if cur_active and not prev_active:
                # edge: OFF -> ON
                #
                # IMPORTANT POLICY:
                # We do NOT auto-enable SAFE_MODE hard-lock file here.
                # HARD_LOCK must be explicit (PANIC / manual), not a side-effect of SAFE turning ON.
                try:
                    if _is_safe_on is not None:
                        if bool(_is_safe_on()):
                            # lock already enabled (explicit) — OK
                            self._safe_hard_lock_ok = True
                            self._safe_hard_lock_error = ""
                        else:
                            # safe active, but no explicit hard-lock file (expected)
                            self._safe_hard_lock_ok = False
                            self._safe_hard_lock_error = "hard-lock not enabled (explicit only)"
                    else:
                        self._safe_hard_lock_ok = False
                        self._safe_hard_lock_error = "safe_lock unavailable"
                except Exception as e:
                    self._safe_hard_lock_ok = False
                    self._safe_hard_lock_error = f"{type(e).__name__}: {e}"

            self._safe_prev_active = cur_active
            
            # STEP1.4.5+: refresh safe_lock status each snapshot (best-effort, без падений)
            try:
                if _is_safe_on is not None:
                    self._safe_lock_on = bool(_is_safe_on())
                    self._safe_lock_error = ""
                else:
                    self._safe_lock_on = None
                    self._safe_lock_error = "safe_lock unavailable"
            except Exception as e:
                self._safe_lock_on = None
                self._safe_lock_error = f"{type(e).__name__}: {e}"
            return {
                "version": self.version,
                "ticks": {
                    sym: {"last": t.last, "bid": t.bid, "ask": t.ask, "ts": t.ts}
                    for sym, t in self.ticks.items()
                },
                # STEP1.4.2: heartbeat meta for UI/core delay detector
                "last_tick_ts": float(getattr(self, "_last_core_tick_ts", 0.0) or 0.0),
                "core_lag_s": core_lag_s,
                "core_stall": core_stall,

                # STEP1.4.3: time integrity flags
                "core_time_backwards": core_time_backwards,
                "core_time_backwards_delta_s": core_time_backwards_delta_s,
                "core_time_backwards_count": core_time_backwards_count,

                # explicit SAFE_MODE policy flag (core-owned)
                "safe_mode_active": bool(safe_mode_active),

                # STEP1.4.4: SafeMode behavior & policy (core owns it, UI consumes it)
                # Дополнение: meta о hard-lock (file SAFE_MODE)
                "safe_mode": (lambda _sm: (
                    _sm.update(
                        {
                            "meta": dict(_sm.get("meta") or {}, **{
                                # edge-trigger enable result
                                "hard_lock_ok": bool(getattr(self, "_safe_hard_lock_ok", False)),
                                "hard_lock_error": str(getattr(self, "_safe_hard_lock_error", "") or ""),

                                # живой статус lock-файла (проверяется каждый snapshot)
                                "safe_lock_on": getattr(self, "_safe_lock_on", None),
                                "safe_lock_error": str(getattr(self, "_safe_lock_error", "") or ""),
                            })
                        }
                    ) or _sm
                ))(sm),

                "health": (lambda: (
                    get_health_snapshot_for_core()
                ))(),

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
        write_stream: bool = True,
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
        now_ts = self._normalize_ts(ts)

        # STEP1.4.2: heartbeat — фиксируем момент последнего core tick
        self.mark_core_tick(now_ts)

        # first real market tick received (unblocks SAFE-start guard)
        self._has_seen_tick = True

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
            # ВАЖНО: при ingest из ticks_stream.jsonl ставим write_stream=False,
            # чтобы не было эха (читатель -> upsert -> запись -> читатель -> ...)
            if write_stream:
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
                    _log_throttled(
                        "ipc_ticks.append_tick",
                        "debug",
                        "ipc_ticks.append_tick failed (tick processed anyway)",
                        interval_s=60.0,
                        exc_info=True,
                    )

            self.version += 1
            new_version = self.version

        # --- вне локов: нотификация TPSL ---
        if self._enable_tpsl and self.tpsl is not None:
            try:
                # TPSLManager ожидает on_price(symbol, price, ts)
                self.tpsl.on_price(sym, float(last_f), now_ts)  # type: ignore[call-arg]
            except Exception:
                # TP/SL не должен ронять основной поток тиков
                _log_throttled(
                    "tpsl.on_price",
                    "warning",
                    "TPSLManager.on_price failed (tick loop continues)",
                    interval_s=30.0,
                    exc_info=True,
                )

        return new_version
        
    # ----------------- core delay detector (STEP1.4.2) -----------------

    def mark_core_tick(self, ts: Optional[float] = None) -> None:
        """Зафиксировать факт 'живого' core-tick (heartbeat) + time integrity."""
        ts_s = self._normalize_ts(ts)
        try:
            self._check_time_integrity(ts_s)
        except Exception:
            _log_throttled(
                "core.time_integrity",
                "warning",
                "core time integrity check failed (heartbeat continues)",
                interval_s=60.0,
                exc_info=True,
            )
        self._last_core_tick_ts = ts_s

    def get_core_lag_s(self, now: Optional[float] = None) -> float:
        """Сколько секунд прошло с последнего core tick."""
        try:
            t_now = float(now) if now is not None else time.time()
        except Exception:
            t_now = time.time()
        try:
            last = float(getattr(self, "_last_core_tick_ts", 0.0) or 0.0)
        except Exception:
            last = 0.0
        return max(0.0, t_now - last)

    def detect_stall(self, threshold_s: Optional[float] = None) -> bool:
        """True, если core tick не приходил дольше threshold_s."""
        try:
            thr = float(threshold_s) if threshold_s is not None else float(self._core_stall_threshold_s)
        except Exception:
            thr = 2.0
        return self.get_core_lag_s() >= max(0.1, thr)
