from __future__ import annotations

import json
import time
import os
import sys
import threading
import subprocess
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
        ui_state: UIState | None,
        uiapi_getter: Callable[[], Any] | None,
        save_sim_state_fn: Callable[[dict], None] | None,
    ) -> None:
        self.app = app
        self.ui_state = ui_state
        self._uiapi_getter = uiapi_getter
        self._save_sim_state = save_sim_state_fn

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

    # ------------------------------------------------------------------ REAL ticks feed (bookTicker)

    def _project_root(self) -> Path:
        # ui/controllers/autosim_controller.py -> ui/controllers -> ui -> ROOT
        return Path(__file__).resolve().parents[2]

    def _runtime_dir(self) -> Path:
        return self._project_root() / "runtime"

    def _get_selected_symbol(self) -> str:
        # UI topbar uses app.var_symbol (tk.StringVar)
        try:
            v = getattr(self.app, "var_symbol", None)
            if v is not None and hasattr(v, "get"):
                s = str(v.get() or "").strip().upper()
                if s:
                    return s
        except Exception:
            pass

        # fallback: sometimes app has symbol attribute
        try:
            s2 = str(getattr(self.app, "symbol", "") or "").strip().upper()
            if s2:
                return s2
        except Exception:
            pass

        return "ADAUSDT"

    def _ticks_proc(self):
        return getattr(self.app, "_ticks_feed_proc", None)

    def _start_ticks_feed_if_needed(self) -> None:
        """
        Start REAL bid/ask stream into runtime/ticks_stream.jsonl using tools/ticks_book_stream.py.
        Safe: if already running -> no-op.
        """
        try:
            p = self._ticks_proc()
            if p is not None:
                try:
                    if p.poll() is None:
                        # already running
                        return
                except Exception:
                    pass

            sym = self._get_selected_symbol()
            root = self._project_root()
            tool = root / "tools" / "ticks_book_stream.py"
            if not tool.exists():
                self._log(f"[TICKS] tool not found: {tool}")
                return

            # ensure runtime dir exists
            try:
                self._runtime_dir().mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

            # log file for the feed
            log_path = self._runtime_dir() / "ticks_feed.log"
            try:
                fp = open(log_path, "a", encoding="utf-8")
            except Exception:
                fp = None

            args = [
                sys.executable,
                str(tool),
                "--reset",
                "--symbols",
                sym,
                "--min-ms",
                "150",
            ]

            creationflags = 0
            if os.name == "nt":
                # no extra console window
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

            proc = subprocess.Popen(
                args,
                cwd=str(root),
                stdout=fp if fp is not None else subprocess.DEVNULL,
                stderr=fp if fp is not None else subprocess.STDOUT,
                creationflags=creationflags,
            )

            setattr(self.app, "_ticks_feed_proc", proc)
            setattr(self.app, "_ticks_feed_log_fp", fp)
            setattr(self.app, "_ticks_feed_symbol", sym)

            self._log(f"[TICKS] REAL feed ON ({sym})")
        except Exception as e:
            self._log(f"[TICKS] start failed: {e}")

    def _stop_ticks_feed_if_running(self) -> None:
        """Stop previously started ticks feed process (best-effort)."""
        try:
            proc = self._ticks_proc()
            if proc is None:
                return

            try:
                if proc.poll() is None:
                    proc.terminate()
            except Exception:
                pass

            # close log file handle if any
            try:
                fp = getattr(self.app, "_ticks_feed_log_fp", None)
                if fp is not None:
                    fp.close()
            except Exception:
                pass

            setattr(self.app, "_ticks_feed_proc", None)
            setattr(self.app, "_ticks_feed_log_fp", None)

            self._log("[TICKS] REAL feed OFF")
        except Exception as e:
            self._log(f"[TICKS] stop failed: {e}")

    # ------------------------------------------------------------------ ticks ingest (tail runtime/ticks_stream.jsonl -> core StateEngine)

    def _ticks_ingest_stop_event(self):
        return getattr(self.app, "_ticks_ingest_stop", None)

    def _start_ticks_ingest_if_needed(self) -> None:
        """
        Start a background thread that tails runtime/ticks_stream.jsonl and pushes ticks into core
        (UIAPI.on_tick(..., write_stream=False)).
        """
        try:
            thr = getattr(self.app, "_ticks_ingest_thread", None)
            if thr is not None and getattr(thr, "is_alive", lambda: False)():
                return

            stop_ev = threading.Event()
            setattr(self.app, "_ticks_ingest_stop", stop_ev)

            def _worker():
                try:
                    root = Path(__file__).resolve().parents[2]
                    stream_path = root / "runtime" / "ticks_stream.jsonl"
                    # ждём появления файла (ticks_book_stream запускается параллельно)
                    t0 = time.time()
                    while not stream_path.exists():
                        if stop_ev.is_set():
                            return
                        if time.time() - t0 > 10.0:
                            # не ждём вечно
                            break
                        time.sleep(0.1)

                    api = None
                    try:
                        api = self.app._ensure_uiapi()
                    except Exception:
                        api = None

                    # tail-file
                    pos = 0
                    while not stop_ev.is_set():
                        if not stream_path.exists():
                            time.sleep(0.2)
                            continue

                        try:
                            with stream_path.open("r", encoding="utf-8", errors="ignore") as f:
                                # если файл был reset/укорочен — начинаем сначала
                                try:
                                    size = stream_path.stat().st_size
                                    if pos > size:
                                        pos = 0
                                except Exception:
                                    pass

                                f.seek(pos)
                                line = f.readline()
                                if not line:
                                    pos = f.tell()
                                    time.sleep(0.15)
                                    continue
                                pos = f.tell()
                        except Exception:
                            time.sleep(0.25)
                            continue

                        line = line.strip()
                        if not line:
                            continue

                        try:
                            obj = json.loads(line)
                        except Exception:
                            continue

                        try:
                            sym = str(obj.get("symbol", "") or "").upper()
                            price = obj.get("price")
                            bid = obj.get("bid")
                            ask = obj.get("ask")
                            ts = obj.get("ts")
                            if not sym or price is None:
                                continue
                        except Exception:
                            continue

                        # lazy re-acquire api if needed
                        if api is None:
                            try:
                                api = self.app._ensure_uiapi()
                            except Exception:
                                api = None

                        if api is None:
                            continue

                        # IMPORTANT: write_stream=False to avoid echo back into ticks_stream.jsonl
                        try:
                            if hasattr(api, "on_tick"):
                                api.on_tick(sym, float(price), bid=bid, ask=ask, ts=ts, write_stream=False)
                            else:
                                # fallback: at least heartbeat
                                api.on_price(sym, float(price), ts=ts)
                        except Exception:
                            continue
                except Exception:
                    return

            t = threading.Thread(target=_worker, name="ticks_ingest", daemon=True)
            setattr(self.app, "_ticks_ingest_thread", t)
            t.start()
            self._log("[TICKS] ingest ON (tail ticks_stream.jsonl -> core)")
        except Exception as e:
            self._log(f"[TICKS] ingest start failed: {e}")

    def _stop_ticks_ingest_if_running(self) -> None:
        try:
            ev = self._ticks_ingest_stop_event()
            if ev is not None:
                try:
                    ev.set()
                except Exception:
                    pass
            setattr(self.app, "_ticks_ingest_stop", None)
            setattr(self.app, "_ticks_ingest_thread", None)
            self._log("[TICKS] ingest OFF")
        except Exception as e:
            self._log(f"[TICKS] ingest stop failed: {e}")

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
        api = self._get_uiapi()
        if api is not None and hasattr(api, "persist_trade_record"):
            for rec in records:
                try:
                    api.persist_trade_record(rec)
                except Exception:
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

    def start(self) -> None:
        """Enable AUTOSIM engine on app + RESUME trading FSM (manual stop OFF)."""
        try:
            # 1) Resume FSM via CommandRouter(policy,fsm)
            try:
                from core.autonomy_policy import AutonomyPolicyStore
                from core.trading_state_machine import TradingStateMachine
                from core.command_router import CommandRouter

                policy = AutonomyPolicyStore()
                fsm = TradingStateMachine()
                r = CommandRouter(policy, fsm).handle("/resume")
                if r is not None and getattr(r, "ok", False):
                    self._log("[CMD] /resume -> OK")
                else:
                    msg = getattr(r, "message", "") if r is not None else "no result"
                    self._log(f"[CMD] /resume -> FAIL: {msg}")
            except Exception as e:
                self._log(f"[CMD] /resume failed: {e}")

            # 2) Enable AUTOSIM engine (previous behavior)
            if getattr(self.app, "_autosim", None) is not None:
                self._log("[AUTOSIM] already ON")
                self._refresh_toggle_button()
                return

            # Start REAL market ticks feed when user presses START
            self._start_ticks_feed_if_needed()
            self._start_ticks_ingest_if_needed()

            factory = getattr(self.app, "_AUTOSIM_FACTORY", None)
            if factory is None:
                self._log("[AUTOSIM] factory not available")
                self._refresh_toggle_button()
                return

            AutoSimFromSignals, AutoSimConfig = factory
            self.app._autosim = AutoSimFromSignals(config=AutoSimConfig())
            self._log("[AUTOSIM] ON")
            self._refresh_toggle_button()
        except Exception as e:
            self._log(f"[AUTOSIM] start failed: {e}")

    def stop(self) -> None:
        """Disable AUTOSIM engine on app + STOP trading FSM (manual stop ON)."""
        try:
            # 1) Disable AUTOSIM engine (previous behavior)
            if getattr(self.app, "_autosim", None) is None:
                self._log("[AUTOSIM] already OFF")
            else:
                self.app._autosim = None
                self._log("[AUTOSIM] OFF")

            # Stop REAL ticks feed when user presses STOP
            self._stop_ticks_feed_if_running()
            self._stop_ticks_ingest_if_running()

            # 2) Manual STOP via CommandRouter(policy,fsm)
            try:
                from core.autonomy_policy import AutonomyPolicyStore
                from core.trading_state_machine import TradingStateMachine
                from core.command_router import CommandRouter

                policy = AutonomyPolicyStore()
                fsm = TradingStateMachine()
                r = CommandRouter(policy, fsm).handle("/stop")
                if r is not None and getattr(r, "ok", False):
                    self._log("[CMD] /stop -> OK")
                else:
                    msg = getattr(r, "message", "") if r is not None else "no result"
                    self._log(f"[CMD] /stop -> FAIL: {msg}")
            except Exception as e:
                self._log(f"[CMD] /stop failed: {e}")

            self._refresh_toggle_button()
        except Exception as e:
            self._log(f"[AUTOSIM] stop failed: {e}")

    def _refresh_toggle_button(self, topbar_view=None) -> None:
        """Update AUTOSIM toggle button text/style (best-effort)."""
        try:
            view = topbar_view if topbar_view is not None else self.app
            btn = getattr(view, "btn_autosim_toggle", None) or getattr(self.app, "btn_autosim_toggle", None)
            if btn is None or not hasattr(btn, "configure"):
                return

            is_on = getattr(self.app, "_autosim", None) is not None
            if is_on:
                btn.configure(text="STOP", style="AutosimOff.TButton")
            else:
                btn.configure(text="START", style="AutosimOn.TButton")
        except Exception:
            return

    def toggle(self) -> None:
        """Toggle AUTOSIM ON/OFF from a single UI button."""
        try:
            if getattr(self.app, "_autosim", None) is None:
                self.start()
            else:
                self.stop()
        finally:
            self._refresh_toggle_button()

    def bind_to_topbar(self, topbar_view) -> None:
        """
        Привязка AUTOSIM Toggle к кнопке.
        Ожидаем атрибут: btn_autosim_toggle на app (или topbar_view).
        """
        try:
            btn = getattr(topbar_view, "btn_autosim_toggle", None) or getattr(self.app, "btn_autosim_toggle", None)

            if btn is not None and hasattr(btn, "configure"):
                btn.configure(command=self.toggle)

            # обновим текст/цвет сразу при старте UI
            self._refresh_toggle_button(topbar_view)

            self._log("[AUTOSIM] topbar bound (toggle)")
        except Exception as e:
            self._log(f"[AUTOSIM] bind_to_topbar failed: {e}")
