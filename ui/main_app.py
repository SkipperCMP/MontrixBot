from __future__ import annotations

import tkinter as tk

from ui.app_step9 import App
from ui.state.ui_state import UIState


def main() -> None:
    """Entry point for MontrixBot UI Trading Desk (STEP1.3.1).

    Пока это просто тонкая обёртка над старым App(tk.Tk),
    но уже с заготовленным UIState, который мы будем
    постепенно протаскивать в layout/controllers.
    """
    ui_state = UIState()

    app = App()  # type: ignore[call-arg]

    # Временный мост: позже мы будем использовать ui_state
    # внутри layout/controllers, а не в самом App.
    app.ui_state = ui_state  # type: ignore[attr-defined]

    app.mainloop()


if __name__ == "__main__":
    main()
