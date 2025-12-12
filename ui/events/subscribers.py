# ui/events/subscribers.py
from __future__ import annotations

from typing import Any

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
        try:
            if isinstance(payload, dict):
                snapshot = payload.get("snapshot")
        except Exception:
            snapshot = None

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

        # 3) сюда же позже добавим подписчиков:
        #    - positions_panel / mini_equity / status_bar (если решим переводить их на события)
        #    - health/log/signal (EVT_HEALTH/EVT_LOG/EVT_SIGNAL)

    event_bus.subscribe(EVT_SNAPSHOT, _on_snapshot)
