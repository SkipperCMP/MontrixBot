"""Headless runner (canonical).

Goal:
  - Provide an explicit, supported "headless" entrypoint that does NOT
    import any UI modules.
  - Keep side-effects minimal: no file writers beyond core runtime artifacts.

This runner currently supports a safe offline smoke scenario:
  python -m scripts.run_headless --smoke

It is intentionally conservative: no real trading, no networking.
"""

from __future__ import annotations

import os
import sys


def _ensure_project_root_on_path() -> None:
    root = os.path.dirname(os.path.dirname(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)


def _run_smoke() -> int:
    """Run offline headless smoke without importing UI."""
    from scripts.smoke_run import main as smoke_main

    try:
        smoke_main()
        return 0
    except PermissionError as e:
        msg = str(e or "")
        # If a headless flow hits the manual confirm surface, be explicit and return exit=2
        if ("confirm required" in msg.lower()) or ("real confirm" in msg.lower()):
            try:
                from core.risky_confirm import RiskyConfirmService

                pc = RiskyConfirmService().request(
                    cmd_text="python -m scripts.run_headless --smoke confirm=<token>",
                    actor="headless",
                )
                print("REAL CONFIRM REQUIRED")
                print("confirm_token:", pc.token)
                print("re-run with: confirm=" + pc.token)
            except Exception:
                print("REAL CONFIRM REQUIRED")
            return 2

        print("PermissionError:", msg)
        return 1
    except SystemExit as e:
        # smoke_run uses sys.exit
        return int(getattr(e, "code", 1) or 0)


def main(argv: list[str] | None = None) -> int:
    _ensure_project_root_on_path()

    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        args = ["--smoke"]

    if "--smoke" in args:
        return _run_smoke()

    print("Unknown args:", " ".join(args))
    print("Usage: python -m scripts.run_headless --smoke")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
