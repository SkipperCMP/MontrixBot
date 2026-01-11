# ui/events/subscribers.py
from __future__ import annotations

from typing import Any
import time

from ui.events.bus import event_bus
from ui.events.types import Event, EVT_SNAPSHOT


def install_default_ui_subscribers(app: Any) -> None:
    """Ставит базовые подписки UI на EventBus (один раз).

    STEP1.3.4_pre3:
    - TickUpdater публикует EVT_SNAPSHOT
    - UI подписчики получают снапшот только через EventBus
    """
    if getattr(app, "_ui_events_installed", False):
        return
    app._ui_events_installed = True

    def _on_snapshot(ev: Event) -> None:
        payload = getattr(ev, "payload", None)
        snapshot = None
        meta = {}
        try:
            if isinstance(payload, dict):
                snapshot = payload.get("snapshot")
                meta = payload.get("meta") or {}
        except Exception:
            snapshot = None
            meta = {}

        if not isinstance(snapshot, dict):
            return

        # 1) chart_controller (если есть)
        try:
            cc = getattr(app, "chart_controller", None)
            if cc is not None and hasattr(cc, "update_from_snapshot"):
                cc.update_from_snapshot(snapshot)
        except Exception:
            pass

        # 2) price/topbar hook (если есть)
        try:
            if hasattr(app, "_update_price_from_snapshot"):
                app._update_price_from_snapshot(snapshot)
        except Exception:
            pass

        # 3) status bar + mini-equity (EVT_SNAPSHOT, best-effort; UI-thread safe via .after())
        try:
            mode = getattr(app, "_mode", "SIM") or "SIM"
            sb = getattr(app, "status_bar", None)
            me = getattr(app, "mini_equity", None)
            portfolio = snapshot.get("portfolio") if isinstance(snapshot.get("portfolio"), dict) else {}

            # STEP1.4.1: heartbeat lag/stall из TickUpdater.meta
            lag_s = None
            try:
                lag_s = meta.get("lag_s") if isinstance(meta, dict) else None
                lag_s = float(lag_s) if lag_s is not None else None
            except Exception:
                lag_s = None

            # STEP1.4.3: fallback lag_s из core snapshot (last_tick_ts)
            if lag_s is None:
                try:
                    last_ts = snapshot.get("last_tick_ts")
                    last_ts = float(last_ts) if last_ts is not None else None
                    if last_ts is not None and last_ts > 0:
                        lag_s = max(0.0, time.time() - last_ts)
                except Exception:
                    pass

            # Прокидываем в snapshot для update_from_snapshot(), даже если StatusBar не имеет отдельных сеттеров
            # STEP1.4.3: time integrity signal from core
            try:
                if snapshot.get("core_time_backwards") is True:
                    snapshot["time_integrity"] = "BACKWARDS"
            except Exception:
                pass
            if lag_s is not None:
                try:
                    snapshot["ui_lag_s"] = lag_s
                    snapshot["_ui_lag_s"] = lag_s
                    snapshot["ui_stall"] = bool(lag_s >= 2.0)
                except Exception:
                    pass

            # STEP1.4.2: прокидываем mode в snapshot, чтобы StatusBar обновлялся одним вызовом
            try:
                snapshot["mode"] = mode
            except Exception:
                pass

            def _apply() -> None:
                # mini_equity
                try:
                    if me is not None and hasattr(me, "update"):
                        me.update(portfolio)
                except Exception:
                    pass

                # status_bar (STEP1.4.2: единый вызов update_from_snapshot)
                try:
                    if sb is None:
                        return
                    if hasattr(sb, "update_from_snapshot"):
                        sb.update_from_snapshot(snapshot)
                except Exception:
                    pass

            try:
                if hasattr(app, "after"):
                    app.after(0, _apply)
                else:
                    _apply()
            except Exception:
                _apply()
        except Exception:
            pass

        # 4) deals journal widget (best-effort)
        try:
            dj = getattr(app, "_deals_journal_widget", None)
            if dj is not None and hasattr(dj, "update_from_snapshot"):
                dj.update_from_snapshot(snapshot)
        except Exception:
            pass

        # 5) сюда же позже добавим подписчиков:
        #    - positions_panel (если решим переводить на события)
        #    - health/log/signal (EVT_HEALTH/EVT_LOG/EVT_SIGNAL)

    event_bus.subscribe(EVT_SNAPSHOT, _on_snapshot)
