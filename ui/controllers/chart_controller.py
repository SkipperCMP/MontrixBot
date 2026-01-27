# ui/controllers/chart_controller.py
from __future__ import annotations

from typing import Any, Callable, Optional

import os
import time
import tkinter as tk
from tkinter import messagebox


class ChartController:
    """Управление RSI / LIVE-окнами с графиками.

    Вынесено из ui.app_step9.App:
    - _open_rsi_chart
    - _open_rsi_live_chart

    Логика загрузки цен остаётся в App._load_chart_prices.
    """

    def __init__(self, app: Any, chart_panel_cls: Optional[Callable[..., Any]]) -> None:
        self.app = app
        self.ChartPanel = chart_panel_cls
        self._last_snapshot: dict | None = None  # STEP1.3.1: hook для TickUpdater

        # Chart-first: embedded panel support (UI-only)
        self._embedded_panel = None
        self._embedded_running = False
        self._embedded_timeframe_s = 60

    # ------------------------------------------------------------------ helpers

    def _ensure_chartpanel(self, title: str) -> Optional[tuple[tk.Toplevel, Any]]:
        """Создаёт окно и ChartPanel, если доступен matplotlib."""
        ChartPanel = self.ChartPanel
        if ChartPanel is None:
            messagebox.showwarning(title, "ChartPanel / matplotlib недоступны.")
            return None

        win = tk.Toplevel(self.app)
        win.title(title)
        win.geometry("800x500")

        panel = ChartPanel(win)
        panel.pack(fill="both", expand=True)

        return win, panel   

    def _ensure_embedded_panel(self) -> Optional[Any]:
        """Ensure embedded ChartPanel exists inside App's chart mount (chart-first)."""
        ChartPanel = self.ChartPanel
        if ChartPanel is None:
            return None

        if self._embedded_panel is not None:
            try:
                # if widget still exists, reuse
                if hasattr(self._embedded_panel, "winfo_exists") and self._embedded_panel.winfo_exists():
                    return self._embedded_panel
            except Exception:
                pass

        mount = getattr(self.app, "_chart_mount", None)
        if mount is None:
            return None

        try:
            panel = ChartPanel(mount)
            panel.pack(fill="both", expand=True)
            self._embedded_panel = panel
            return panel
        except Exception:
            return None

    # ---------------------------------------------------------------- indicators (UI-only)

    def _ui_rsi_enabled(self) -> bool:
        try:
            v = getattr(self.app, "var_chart_rsi_on", None)
            if v is None:
                return True
            return bool(v.get())
        except Exception:
            return True

    def _ui_macd_enabled(self) -> bool:
        try:
            v = getattr(self.app, "var_chart_macd_on", None)
            if v is None:
                return True
            return bool(v.get())
        except Exception:
            return True

    def _refresh_indicator_labels(self) -> None:
        """Update button labels: Indicators (ON/OFF/MIX), RSI, MACD."""
        rsi_on = self._ui_rsi_enabled()
        macd_on = self._ui_macd_enabled()

        # RSI / MACD labels
        try:
            v = getattr(self.app, "var_chart_rsi_label", None)
            if v is not None:
                v.set("RSI: ON" if rsi_on else "RSI: OFF")
        except Exception:
            pass
        try:
            v = getattr(self.app, "var_chart_macd_label", None)
            if v is not None:
                v.set("MACD: ON" if macd_on else "MACD: OFF")
        except Exception:
            pass

        # Master label
        try:
            lab = getattr(self.app, "var_chart_indicators_label", None)
            if lab is not None:
                if rsi_on and macd_on:
                    lab.set("Indicators: ON")
                elif (not rsi_on) and (not macd_on):
                    lab.set("Indicators: OFF")
                else:
                    lab.set("Indicators: MIX")
        except Exception:
            pass

        # Keep legacy bool var (best-effort)
        try:
            legacy = getattr(self.app, "var_chart_indicators_on", None)
            if legacy is not None:
                legacy.set(bool(rsi_on and macd_on))
        except Exception:
            pass

    def apply_ui_indicators_to_embedded(self) -> None:
        """Apply UI indicator toggles (RSI/MACD) to embedded ChartPanel."""
        panel = getattr(self, "_embedded_panel", None)
        if panel is None:
            return
        try:
            if hasattr(panel, "set_indicator_flags"):
                panel.set_indicator_flags(enable_rsi=self._ui_rsi_enabled(), enable_macd=self._ui_macd_enabled())
        except Exception:
            return

    # Backward-compatible name (old button, old callers)
    def toggle_ui_indicators(self) -> None:
        self.toggle_ui_indicators_master()

    def toggle_ui_indicators_master(self) -> None:
        """Master toggle:
        - if both ON -> turn both OFF
        - else -> turn both ON
        """
        try:
            rsi = getattr(self.app, "var_chart_rsi_on", None)
            macd = getattr(self.app, "var_chart_macd_on", None)
            if rsi is None or macd is None:
                return
            both_on = bool(rsi.get()) and bool(macd.get())
            new_val = not both_on
            rsi.set(bool(new_val))
            macd.set(bool(new_val))
        except Exception:
            return

        self._refresh_indicator_labels()
        self.apply_ui_indicators_to_embedded()

    def toggle_ui_rsi(self) -> None:
        try:
            rsi = getattr(self.app, "var_chart_rsi_on", None)
            if rsi is None:
                return
            rsi.set(not bool(rsi.get()))
        except Exception:
            return

        self._refresh_indicator_labels()
        self.apply_ui_indicators_to_embedded()

    def toggle_ui_macd(self) -> None:
        try:
            macd = getattr(self.app, "var_chart_macd_on", None)
            if macd is None:
                return
            macd.set(not bool(macd.get()))
        except Exception:
            return

        self._refresh_indicator_labels()
        self.apply_ui_indicators_to_embedded()

    # ---------------------------------------------------------------- render mode (UI-only)

    def _ui_render_mode(self) -> str:
        """Return UI render mode: FULL or LIGHT (session-only)."""
        try:
            v = getattr(self.app, "var_chart_render_mode", None)
            if v is None:
                return "FULL"
            m = str(v.get() or "").strip().upper()
            return "LIGHT" if m in ("LIGHT", "L") else "FULL"
        except Exception:
            return "FULL"

    def _refresh_render_label(self) -> None:
        try:
            lab = getattr(self.app, "var_chart_render_label", None)
            if lab is not None:
                lab.set(f"Render: {self._ui_render_mode()}")
        except Exception:
            pass

    def apply_ui_render_to_embedded(self) -> None:
        panel = getattr(self, "_embedded_panel", None)
        if panel is None:
            return
        try:
            if hasattr(panel, "set_render_mode"):
                panel.set_render_mode(self._ui_render_mode())
        except Exception:
            return

    def toggle_ui_render_mode(self) -> None:
        """Toggle FULL <-> LIGHT (UI-only, no runtime writes)."""
        try:
            v = getattr(self.app, "var_chart_render_mode", None)
            if v is None:
                return
            cur = str(v.get() or "").strip().upper()
            new = "LIGHT" if cur not in ("LIGHT", "L") else "FULL"
            v.set(new)
        except Exception:
            return

        self._refresh_render_label()
        self.apply_ui_render_to_embedded()

    def open_candles_embedded(self, timeframe_s: int = 60) -> None:
        """Chart-first: run LIVE candles inside embedded Chart tab (no pop-up)."""
        panel = self._ensure_embedded_panel()
        if panel is None:
            # fallback to legacy pop-out behavior
            self.open_candles_live_chart(timeframe_s)
            return

        # Apply current UI indicator toggles immediately on open
        try:
            self._refresh_indicator_labels()
        except Exception:
            pass
        self.apply_ui_indicators_to_embedded()

        # Apply current UI render mode immediately on open
        try:
            self._refresh_render_label()
        except Exception:
            pass
        self.apply_ui_render_to_embedded()

        # mark running and store TF; reuse existing refresh loop via app.after
        self._embedded_running = True
        self._embedded_timeframe_s = int(timeframe_s or 60)

        # Start a refresh loop by calling the existing pop-out logic on the embedded panel,
        # but without creating a Toplevel. We implement a small local loop here that calls
        # App._load_chart_ohlc and ChartPanel.plot_candles exactly like pop-out version.
        last_levels_sig = None
        last_good_candles = None
        last_good_levels = None
        last_good_trades = None

        # v2.3.11.6 — redraw throttle + gate (UI-only)
        try:
            _throttle_ms = int(str(os.environ.get("MB_UI_CHART_REDRAW_THROTTLE_MS", "350")).strip() or "350")
        except Exception:
            _throttle_ms = 350
        _throttle_ms = max(250, min(500, _throttle_ms))

        _last_render_ts_last = 0
        _last_render_at_s = 0.0

        def refresh() -> None:
            nonlocal last_levels_sig, last_good_candles, last_good_levels, last_good_trades

            if not self._embedded_running:
                return

            try:
                data = self.app._load_chart_ohlc(self._embedded_timeframe_s, max_candles=200, max_ticks=5000)
                raw_candles = (data or {}).get("candles") or []

                reason = ""
                source = ""
                try:
                    reason = str((data or {}).get("reason") or "").strip()
                except Exception:
                    reason = ""
                try:
                    source = str((data or {}).get("source") or "").strip()
                except Exception:
                    source = ""

                candles = []
                debug_meta = None
                try:
                    tf_ms = int(self._embedded_timeframe_s) * 1000
                    if tf_ms <= 0:
                        tf_ms = 60_000

                    items = []
                    raw_ts = []

                    for c in (raw_candles or []):
                        if not isinstance(c, dict):
                            continue
                        try:
                            ts = int(c.get("ts_open_ms") or 0)
                        except Exception:
                            ts = 0

                        if 0 < ts < 10**11:
                            ts *= 1000

                        if ts > 0:
                            try:
                                c["ts_open_ms"] = ts
                            except Exception:
                                pass
                            items.append((ts, c))
                            raw_ts.append(ts)

                    if items:
                        items.sort(key=lambda x: x[0])
                        by_ts = {}
                        for ts, c in items:
                            by_ts[ts] = c
                        uniq_ts = sorted(by_ts.keys())
                        candles = [by_ts[ts] for ts in uniq_ts]

                        try:
                            ts_last = int(candles[-1].get("ts_open_ms") or 0)
                        except Exception:
                            ts_last = 0

                        if ts_last > 0:
                            keep_span = int((len(candles) + 5) * tf_ms)
                            cutoff = ts_last - keep_span
                            candles = [
                                c for c in candles
                                if isinstance(c, dict) and int(c.get("ts_open_ms") or 0) >= cutoff
                            ]

                        if uniq_ts:
                            debug_meta = {
                                "ts0": int(candles[0].get("ts_open_ms") or uniq_ts[0]) if candles else uniq_ts[0],
                                "ts_last": int(candles[-1].get("ts_open_ms") or uniq_ts[-1]) if candles else uniq_ts[-1],
                                "n": len(candles) if candles else len(uniq_ts),
                                "raw": len(raw_ts),
                                "dupes": max(0, len(raw_ts) - len(uniq_ts)),
                                "tf_ms": int(tf_ms),
                                "reason": reason,
                                "source": source,
                            }
                except Exception:
                    candles = []
                    debug_meta = None

                # Even with empty candles, show honest HUD (reason/source) in the panel (throttled)
                if not candles:
                    try:
                        tf_ms_hint = int(self._embedded_timeframe_s) * 1000
                        if tf_ms_hint <= 0:
                            tf_ms_hint = 60_000
                    except Exception:
                        tf_ms_hint = 60_000

                    try:
                        if debug_meta is None:
                            debug_meta = {"tf_ms": int(tf_ms_hint), "reason": reason, "source": source}
                        else:
                            debug_meta.setdefault("reason", reason)
                            debug_meta.setdefault("source", source)
                            debug_meta.setdefault("tf_ms", int(tf_ms_hint))
                    except Exception:
                        pass

                    try:
                        now_s = time.time()
                        if (now_s - _last_render_at_s) * 1000.0 >= float(_throttle_ms):
                            _last_render_at_s = now_s
                            panel.plot_candles([], levels=None, trades=None, debug_meta=debug_meta)
                    except Exception:
                        pass

                if candles:
                    # Levels
                    levels = None
                    try:
                        sym = ""
                        try:
                            sym = (self.app.var_symbol.get().strip() or "").upper()
                        except Exception:
                            sym = ""

                        api = None
                        try:
                            if hasattr(self.app, "_ensure_uiapi"):
                                api = self.app._ensure_uiapi()
                        except Exception:
                            api = None

                        def _as_pos_float(x: object) -> float | None:
                            try:
                                v = float(x)
                                return v if v > 0 else None
                            except Exception:
                                return None

                        lv = None
                        if api is not None and hasattr(api, "get_state_snapshot") and sym:
                            se_snap = api.get_state_snapshot() or {}
                            positions = se_snap.get("positions") or {}
                            pos = positions.get(sym) or None
                            if isinstance(pos, dict):
                                entry = _as_pos_float(pos.get("entry_price", pos.get("entry")))
                                tp = _as_pos_float(pos.get("tp"))
                                sl = _as_pos_float(pos.get("sl"))
                                if entry is not None or tp is not None or sl is not None:
                                    lv = {}
                                    if entry is not None:
                                        lv["entry"] = entry
                                    if tp is not None:
                                        lv["tp"] = tp
                                    if sl is not None:
                                        lv["sl"] = sl

                        if lv:
                            levels = lv
                            try:
                                sig = (sym, tuple(sorted(lv.items())))
                                if sig != last_levels_sig:
                                    last_levels_sig = sig
                                    if hasattr(self.app, "_log"):
                                        self.app._log(f"[CHART] {sym} levels: {lv}")
                            except Exception:
                                pass
                    except Exception:
                        levels = None

                    # Trades
                    trades_for_chart = None
                    try:
                        sym = ""
                        try:
                            sym = (self.app.var_symbol.get().strip() or "").upper()
                        except Exception:
                            sym = ""

                        api = None
                        try:
                            if hasattr(self.app, "_ensure_uiapi"):
                                api = self.app._ensure_uiapi()
                        except Exception:
                            api = None

                        tf_ms = int(self._embedded_timeframe_s) * 1000
                        ts0 = int((candles[0] or {}).get("ts_open_ms") or 0)
                        ts1 = int((candles[-1] or {}).get("ts_open_ms") or 0) + tf_ms

                        if api is not None and hasattr(api, "get_trades_for_range") and sym and tf_ms > 0 and ts0 > 0 and ts1 > ts0:
                            raw = api.get_trades_for_range(sym, ts0, ts1, limit=5000) or []

                            by_idx = {}
                            for tr in raw:
                                try:
                                    tms = int(tr.get("ts_ms") or 0)
                                    side = str(tr.get("side") or "").upper().strip()
                                    price = float(tr.get("price") or 0.0)
                                except Exception:
                                    continue
                                if tms <= 0 or price <= 0 or side not in ("BUY", "SELL"):
                                    continue
                                idx = int((tms - ts0) // tf_ms)
                                if idx < 0 or idx >= len(candles):
                                    continue
                                by_idx.setdefault(idx, []).append({"ts_ms": tms, "side": side, "price": price})

                            if by_idx:
                                markers = []
                                for idx, items in by_idx.items():
                                    try:
                                        items = sorted(items, key=lambda x: int(x.get("ts_ms") or 0))
                                    except Exception:
                                        pass
                                    n = len(items)
                                    for j, it in enumerate(items):
                                        off = 0.0
                                        try:
                                            if n > 1:
                                                off = (j - (n - 1) / 2.0) * 0.12
                                        except Exception:
                                            off = 0.0
                                        markers.append(
                                            {
                                                "x": float(idx) + float(off),
                                                "y": float(it.get("price")),
                                                "side": str(it.get("side")),
                                                "ts_ms": int(it.get("ts_ms") or 0),
                                            }
                                        )
                                trades_for_chart = markers
                    except Exception:
                        trades_for_chart = None

                    # Freeze on STALE (same contract as pop-out)
                    is_stale = False
                    try:
                        now_ms = int(__import__("time").time() * 1000)
                        ts_last = 0
                        tf_ms = int(self._embedded_timeframe_s) * 1000

                        try:
                            if debug_meta and int(debug_meta.get("ts_last") or 0) > 0:
                                ts_last = int(debug_meta.get("ts_last") or 0)
                        except Exception:
                            ts_last = 0

                        if ts_last > 0 and tf_ms > 0:
                            age_ms = max(0, now_ms - ts_last)
                            thr = max(int(2 * tf_ms), 120_000)
                            if age_ms > thr:
                                is_stale = True
                    except Exception:
                        is_stale = False

                    if is_stale:
                        if last_good_candles:
                            candles = last_good_candles
                        if last_good_levels is not None:
                            levels = last_good_levels
                        if last_good_trades is not None:
                            trades_for_chart = last_good_trades
                    else:
                        try:
                            last_good_candles = list(candles) if candles else None
                        except Exception:
                            last_good_candles = candles
                        last_good_levels = levels
                        last_good_trades = trades_for_chart

                    # v2.3.11.6 — redraw only on ts_last change + throttled (UI-only)
                    try:
                        now_s = time.time()
                        ts_last_gate = 0
                        try:
                            if debug_meta and int(debug_meta.get("ts_last") or 0) > 0:
                                ts_last_gate = int(debug_meta.get("ts_last") or 0)
                        except Exception:
                            ts_last_gate = 0

                        do_draw = False
                        if ts_last_gate > 0 and ts_last_gate != _last_render_ts_last:
                            if (now_s - _last_render_at_s) * 1000.0 >= float(_throttle_ms):
                                do_draw = True
                        elif ts_last_gate <= 0:
                            # unknown ts_last -> allow throttled draw
                            if (now_s - _last_render_at_s) * 1000.0 >= float(_throttle_ms):
                                do_draw = True

                        if do_draw:
                            _last_render_at_s = now_s
                            if ts_last_gate > 0:
                                _last_render_ts_last = ts_last_gate
                            panel.plot_candles(
                                candles,
                                levels=levels,
                                trades=trades_for_chart,
                                debug_meta=debug_meta,
                            )
                    except Exception:
                        panel.plot_candles(
                            candles,
                            levels=levels,
                            trades=trades_for_chart,
                            debug_meta=debug_meta,
                        )
            except Exception:
                pass

            try:
                self.app.after(int(_throttle_ms), refresh)
            except Exception:
                return

        try:
            refresh()
        except Exception:
            return

    # ------------------------------------------------------------------ API
    
    def update_from_snapshot(self, snapshot: dict | None) -> None:
        """Получает снапшот ядра от TickUpdater.

        Текущая версия:
        - просто запоминает снапшот и версию;
        - не трогает существующую логику обновления графика.

        Позже сюда можно будет добавить:
        - обновление буфера тиков;
        - триггер мягкого перерисовывания LIVE-чарта.
        """
        if snapshot is None:
            return

        try:
            # сохраняем последний снапшот для возможного дальнейшего использования
            self._last_snapshot = dict(snapshot)
        except Exception:
            # защита от странных типов / прокси
            self._last_snapshot = snapshot

    def open_rsi_chart(self) -> None:
        """Открыть статический RSI-график (demo)."""
        res = self._ensure_chartpanel("MontrixBot — RSI Chart (demo 1.1)")
        if res is None:
            return
        win, panel = res

        try:
            times, prices = self.app._load_chart_prices(max_points=300)
            if times and prices:
                panel.plot_series(times, prices)
        except Exception as e:  # noqa: BLE001
            try:
                messagebox.showwarning("RSI Chart", f"Ошибка построения графика: {e!r}")
            except Exception:
                pass

    def open_rsi_live_chart(self) -> None:
        """Открыть LIVE-график с периодическим обновлением."""
        res = self._ensure_chartpanel("MontrixBot — LIVE Chart (ticks=300)")
        if res is None:
            return
        win, panel = res

        def refresh() -> None:
            if not win.winfo_exists():
                return
            try:
                times, prices = self.app._load_chart_prices(max_points=300)
                if times and prices:
                    panel.plot_series(times, prices)
            except Exception:
                # поведение такое же, как и было: молча пропускаем ошибку отрисовки
                pass
            else:
                # планируем следующий апдейт, пока окно живо
                try:
                    win.after(int(_throttle_ms), refresh)
                except Exception:
                    return

        try:
            refresh()
        except Exception:
            # если первый вызов не удался, просто не запускаем цикл
            return

    def open_candles_live_chart(self, timeframe_s: int = 60) -> None:
        """Открыть LIVE-свечной график (OHLC) на основе UIAPI.get_ohlc_series()."""
        res = self._ensure_chartpanel(f"MontrixBot — LIVE Candles ({timeframe_s}s)")
        if res is None:
            return
        win, panel = res
        last_levels_sig = None  # чтобы не спамить лог одинаковыми уровнями

        # UI-only freeze cache: last "good" frame (non-stale)
        last_good_candles = None
        last_good_levels = None
        last_good_trades = None

        # v2.3.11.6 — redraw throttle + gate (UI-only)
        try:
            _throttle_ms = int(str(os.environ.get("MB_UI_CHART_REDRAW_THROTTLE_MS", "350")).strip() or "350")
        except Exception:
            _throttle_ms = 350
        _throttle_ms = max(250, min(500, _throttle_ms))

        _last_render_ts_last = 0
        _last_render_at_s = 0.0

        def refresh() -> None:
            nonlocal last_levels_sig
            if not win.winfo_exists():
                return

            try:
                data = self.app._load_chart_ohlc(timeframe_s, max_candles=200, max_ticks=5000)
                raw_candles = (data or {}).get("candles") or []

                # Normalize + sort + dedupe + drop outliers (UI-only)
                candles = []
                debug_meta = None
                try:
                    tf_ms = int(timeframe_s) * 1000
                    if tf_ms <= 0:
                        tf_ms = 60_000

                    items = []
                    raw_ts = []

                    for c in (raw_candles or []):
                        if not isinstance(c, dict):
                            continue
                        try:
                            ts = int(c.get("ts_open_ms") or 0)
                        except Exception:
                            ts = 0

                        # normalize seconds -> ms
                        if 0 < ts < 10**11:
                            ts *= 1000

                        if ts > 0:
                            # write back normalized ts into candle dict (UI-only)
                            try:
                                c["ts_open_ms"] = ts
                            except Exception:
                                pass
                            items.append((ts, c))
                            raw_ts.append(ts)

                    if items:
                        items.sort(key=lambda x: x[0])

                        by_ts = {}
                        for ts, c in items:
                            by_ts[ts] = c

                        uniq_ts = sorted(by_ts.keys())
                        candles = [by_ts[ts] for ts in uniq_ts]

                        # drop extreme outliers (wrong-day / wrong-clock buckets)
                        try:
                            ts_last = int(candles[-1].get("ts_open_ms") or 0)
                        except Exception:
                            ts_last = 0

                        if ts_last > 0:
                            keep_span = int((len(candles) + 5) * tf_ms)
                            cutoff = ts_last - keep_span
                            candles = [
                                c for c in candles
                                if isinstance(c, dict) and int(c.get("ts_open_ms") or 0) >= cutoff
                            ]

                        if uniq_ts:
                            debug_meta = {
                                "ts0": int(candles[0].get("ts_open_ms") or uniq_ts[0]) if candles else uniq_ts[0],
                                "ts_last": int(candles[-1].get("ts_open_ms") or uniq_ts[-1]) if candles else uniq_ts[-1],
                                "n": len(candles) if candles else len(uniq_ts),
                                "raw": len(raw_ts),
                                "dupes": max(0, len(raw_ts) - len(uniq_ts)),
                                "tf_ms": int(tf_ms),
                            }
                except Exception:
                    candles = []
                    debug_meta = None

                if candles:
                    # Pull ENTRY/TP/SL from core StateEngine snapshot (UI-only, read-only)
                    levels = None
                    try:
                        sym = ""
                        try:
                            sym = (self.app.var_symbol.get().strip() or "").upper()
                        except Exception:
                            sym = ""

                        api = None
                        try:
                            if hasattr(self.app, "_ensure_uiapi"):
                                api = self.app._ensure_uiapi()
                        except Exception:
                            api = None

                        def _as_pos_float(x: object) -> float | None:
                            try:
                                v = float(x)
                                return v if v > 0 else None
                            except Exception:
                                return None

                        lv = None
                        if api is not None and hasattr(api, "get_state_snapshot") and sym:
                            se_snap = api.get_state_snapshot() or {}
                            positions = se_snap.get("positions") or {}
                            pos = positions.get(sym) or None
                            if isinstance(pos, dict):
                                entry = _as_pos_float(pos.get("entry_price", pos.get("entry")))
                                tp = _as_pos_float(pos.get("tp"))
                                sl = _as_pos_float(pos.get("sl"))
                                # UI contract: ChartPanel ожидает уровни с ключами
                                # "entry" / "tp" / "sl" (lowercase).
                                if entry is not None or tp is not None or sl is not None:
                                    lv = {}
                                    if entry is not None:
                                        lv["entry"] = entry
                                    if tp is not None:
                                        lv["tp"] = tp
                                    if sl is not None:
                                        lv["sl"] = sl

                        if lv:
                            levels = lv
                            try:
                                sig = (sym, tuple(sorted(lv.items())))
                                if sig != last_levels_sig:
                                    last_levels_sig = sig
                                    if hasattr(self.app, "_log"):
                                        self.app._log(f"[CHART] {sym} levels: {lv}")
                            except Exception:
                                pass
                    except Exception:
                        levels = None

                    # Trade markers (BUY/SELL) from trades.jsonl (core-owned via UIAPI)
                    trades_for_chart = None
                    try:
                        sym = ""
                        try:
                            sym = (self.app.var_symbol.get().strip() or "").upper()
                        except Exception:
                            sym = ""

                        api = None
                        try:
                            if hasattr(self.app, "_ensure_uiapi"):
                                api = self.app._ensure_uiapi()
                        except Exception:
                            api = None

                        tf_ms = int(timeframe_s) * 1000
                        ts0 = int((candles[0] or {}).get("ts_open_ms") or 0)
                        ts1 = int((candles[-1] or {}).get("ts_open_ms") or 0) + tf_ms

                        if api is not None and hasattr(api, "get_trades_for_range") and sym and tf_ms > 0 and ts0 > 0 and ts1 > ts0:
                            raw = api.get_trades_for_range(sym, ts0, ts1, limit=5000) or []

                            by_idx = {}
                            for tr in raw:
                                try:
                                    tms = int(tr.get("ts_ms") or 0)
                                    side = str(tr.get("side") or "").upper().strip()
                                    price = float(tr.get("price") or 0.0)
                                except Exception:
                                    continue
                                if tms <= 0 or price <= 0 or side not in ("BUY", "SELL"):
                                    continue
                                idx = int((tms - ts0) // tf_ms)
                                if idx < 0 or idx >= len(candles):
                                    continue
                                by_idx.setdefault(idx, []).append({"ts_ms": tms, "side": side, "price": price})

                            if by_idx:
                                markers = []
                                for idx, items in by_idx.items():
                                    try:
                                        items = sorted(items, key=lambda x: int(x.get("ts_ms") or 0))
                                    except Exception:
                                        pass
                                    n = len(items)
                                    for j, it in enumerate(items):
                                        off = 0.0
                                        try:
                                            if n > 1:
                                                off = (j - (n - 1) / 2.0) * 0.12
                                        except Exception:
                                            off = 0.0
                                        markers.append(
                                            {
                                                "x": float(idx) + float(off),
                                                "y": float(it.get("price")),
                                                "side": str(it.get("side")),
                                                "ts_ms": int(it.get("ts_ms") or 0),
                                            }
                                        )
                                trades_for_chart = markers
                    except Exception:
                        trades_for_chart = None

                    # UI-only: freeze candles/levels/trades when STALE detected
                    is_stale = False
                    try:
                        now_ms = int(time.time() * 1000)
                        ts_last = 0
                        tf_ms = int(timeframe_s) * 1000

                        try:
                            if debug_meta and int(debug_meta.get("ts_last") or 0) > 0:
                                ts_last = int(debug_meta.get("ts_last") or 0)
                        except Exception:
                            ts_last = 0

                        if ts_last > 0 and tf_ms > 0:
                            age_ms = max(0, now_ms - ts_last)
                            thr = max(int(2 * tf_ms), 120_000)  # same spirit as ChartPanel
                            if age_ms > thr:
                                is_stale = True
                    except Exception:
                        is_stale = False

                    if is_stale:
                        # Keep last good frame if available
                        if last_good_candles:
                            candles = last_good_candles
                        if last_good_levels is not None:
                            levels = last_good_levels
                        if last_good_trades is not None:
                            trades_for_chart = last_good_trades
                    else:
                        # Update freeze cache
                        try:
                            last_good_candles = list(candles) if candles else None
                        except Exception:
                            last_good_candles = candles
                        last_good_levels = levels
                        last_good_trades = trades_for_chart

                    # v2.3.11.6 — redraw only on ts_last change + throttled (UI-only)
                    try:
                        now_s = time.time()
                        ts_last_gate = 0
                        try:
                            if debug_meta and int(debug_meta.get("ts_last") or 0) > 0:
                                ts_last_gate = int(debug_meta.get("ts_last") or 0)
                        except Exception:
                            ts_last_gate = 0

                        do_draw = False
                        if ts_last_gate > 0 and ts_last_gate != _last_render_ts_last:
                            if (now_s - _last_render_at_s) * 1000.0 >= float(_throttle_ms):
                                do_draw = True
                        elif ts_last_gate <= 0:
                            # unknown ts_last -> allow throttled draw
                            if (now_s - _last_render_at_s) * 1000.0 >= float(_throttle_ms):
                                do_draw = True

                        if do_draw:
                            _last_render_at_s = now_s
                            if ts_last_gate > 0:
                                _last_render_ts_last = ts_last_gate
                            panel.plot_candles(
                                candles,
                                levels=levels,
                                trades=trades_for_chart,
                                debug_meta=debug_meta,
                            )
                    except Exception:
                        panel.plot_candles(
                            candles,
                            levels=levels,
                            trades=trades_for_chart,
                            debug_meta=debug_meta,
                        )

            except Exception:
                # UI-only: silently ignore render errors
                pass

            try:
                win.after(1000, refresh)
            except Exception:
                return

        try:
            refresh()
        except Exception:
            return
