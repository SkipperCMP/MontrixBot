# ui/controllers/mode_controller.py
from __future__ import annotations

from pathlib import Path
from typing import Any

import tkinter as tk


class ModeController:
    """Управление режимом UI (SIM/REAL), SAFE и Dry-Run бейджами.

    Вся логика переключения и обновления индикаторов вынесена сюда
    из ui.app_step9.App, чтобы сам App оставался тонким слоем-клеем.
    """

    def __init__(self, app: Any, safe_file: Path) -> None:
        self.app = app
        self.safe_file = safe_file

    # --- SAFE -------------------------------------------------------------

    def safe_is_on(self) -> bool:
        """Проверка SAFE-флага через SAFE_FILE."""
        try:
            return self.safe_file.exists()
        except Exception:
            return False

    def refresh_safe_badge(self) -> None:
        """Обновляет SAFE-бейдж и доступность кнопки Close."""
        app = self.app

        app.safe_on = self.safe_is_on()
        if app.safe_on:
            app.badge_safe.configure(text="SAFE", style="BadgeSafe.TLabel")
        else:
            app.badge_safe.configure(text="SAFE OFF", style="BadgeDanger.TLabel")

        # SAFE блокирует только REAL-закрытие
        mode = getattr(app, "_mode", "SIM")
        if mode == "REAL":
            app.btn_close.configure(state="disabled" if app.safe_on else "normal")
        else:
            app.btn_close.configure(state="normal")

    def toggle_safe(self) -> None:
        """Переключение SAFE_MODE по клику на бейдже."""
        app = self.app

        try:
            if self.safe_file.exists():
                # выключаем SAFE
                try:
                    self.safe_file.unlink()
                except FileNotFoundError:
                    pass
                app._log("[SAFE] SAFE_MODE disabled via UI (REAL close allowed)")
            else:
                self.safe_file.touch()
                app._log("[SAFE] SAFE_MODE enabled via UI (REAL close blocked)")
        except Exception as e:  # noqa: BLE001
            try:
                app._log(f"[SAFE][ERR] cannot toggle SAFE_MODE: {e!r}")
            except Exception:
                pass

        # обновляем бейдж и состояние кнопки Close
        try:
            self.refresh_safe_badge()
        except Exception:
            pass

    # --- Dry-Run ----------------------------------------------------------

    def refresh_dry_badge(self) -> None:
        """Обновляет внешний вид бейджа Dry-Run по app.dry_run_ui_on."""
        app = self.app
        badge = getattr(app, "badge_dry", None)
        if badge is None:
            return

        try:
            val = bool(getattr(app, "dry_run_ui_on", True))
        except Exception:
            val = True
        app.dry_run_ui_on = val

        text = "Dry-Run" if val else "REAL CLI"
        style = "BadgeWarn.TLabel" if val else "BadgeDanger.TLabel"

        try:
            badge.configure(text=text, style=style)
        except tk.TclError:
            return

    def toggle_dry(self) -> None:
        """Переключение Dry-Run бейджа (влияет на UI и логи)."""
        app = self.app
        try:
            current = bool(getattr(app, "dry_run_ui_on", True))
        except Exception:
            current = True
        app.dry_run_ui_on = not current

        state = "ON" if app.dry_run_ui_on else "OFF"
        try:
            app._log(
                f"[DRY] Dry-Run badge toggled to {state} "
                "(for UI only, CLI still uses --ask)"
            )
        except Exception:
            pass

        try:
            self.refresh_dry_badge()
        except Exception:
            pass

    # --- Mode SIM / REAL --------------------------------------------------

    def set_mode(self, mode: str) -> None:
        """Переключение режима UI: SIM или REAL."""
        app = self.app

        mode = (mode or "SIM").upper()
        app._mode = mode

        if hasattr(app, "var_mode"):
            app.var_mode.set(f"Mode: {mode}")

        # Перепривязываем команды кнопок в зависимости от режима
        if mode == "SIM":
            app.btn_buy.configure(command=app.on_buy_sim)
            app.btn_close.configure(command=app.on_close_sim)
        else:
            app.btn_buy.configure(command=app.on_buy_real)
            app.btn_close.configure(command=app.on_close_real)

        # После смены режима обновим SAFE-индикацию
        try:
            self.refresh_safe_badge()
        except Exception:
            pass

    def toggle_mode(self) -> None:
        """Переключить режим SIM/REAL и синхронизировать его с UIAPI."""
        app = self.app

        new_mode = "REAL" if getattr(app, "_mode", "SIM") == "SIM" else "SIM"
        self.set_mode(new_mode)

        # Если UIAPI уже создан, обновляем режим и в ядре
        api = getattr(app, "_uiapi", None)
        if api is not None:
            try:
                api.set_mode(new_mode)
            except Exception:
                pass

        try:
            app._log(f"[UI] switched mode to {new_mode}")
        except Exception:
            pass
