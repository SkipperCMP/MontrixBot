from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)


def activate_panic(reason: str = "panic") -> None:
    """
    Single PANIC entrypoint for the whole app.

    IMPORTANT:
    - Best-effort: must never raise.
    - Calls runtime.panic_tools under the hood.
    """
    try:
        from runtime.panic_tools import activate_panic as _activate  # runtime-owned
        _activate(reason)
    except Exception:
        try:
            log.exception("core.panic_facade.activate_panic failed (ignored)")
        except Exception:
            pass


def is_panic_active() -> bool:
    """
    Single PANIC status checker for the whole app.

    IMPORTANT:
    - Best-effort: must never raise.
    """
    try:
        from runtime.panic_tools import is_panic_active as _is_active  # runtime-owned
        return bool(_is_active())
    except Exception:
        return False
