from __future__ import annotations

# Canonical UI entrypoint:
# - ui.main_app: entrypoint
# - ui.app_ui: implementation
#
# Legacy ui.app_step9 is canon-disabled and must not be imported here.

from ui.app_ui import App
from ui.state.ui_state import UIState

from core.event_spine import ensure_event_spine


def launch() -> None:
    """Backward-compatible alias used by scripts/tests."""
    main()


def main() -> None:
    """Entry point for MontrixBot UI Trading Desk (canonical)."""
    # PRODUCT-MODE: install core event spine (idempotent)
    try:
        ensure_event_spine()
    except Exception:
        pass

    # v2.3.9 hotfix: initialize core notification center (best-effort)
    try:
        from core.notifications_center import get_notification_center
        get_notification_center().emit_now("INFO", "system", "ui_started", meta={"source": "ui"})
    except Exception:
        pass
        
    ui_state = UIState()

    app = App()  # type: ignore[call-arg]

    # Temporary bridge: ui_state will be threaded deeper into controllers/layout later.
    app.ui_state = ui_state  # type: ignore[attr-defined]

    app.mainloop()


if __name__ == "__main__":
    main()
