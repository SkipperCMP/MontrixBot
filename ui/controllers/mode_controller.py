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

    def _get_safe_snapshot(self) -> dict:
        """
        SAFE MODE snapshot приходит из core через ui_api.get_state_snapshot():
            snapshot["safe_mode"] = { active, severity, reason, reasons, policy{deny_actions,...}, ... }
        UI не читает никаких файлов и не управляет SAFE напрямую.
        """
        app = self.app

        # 1) Если где-то в app уже сохранён последний снапшот — используем его
        snap = getattr(app, "_last_core_snapshot", None)
        if isinstance(snap, dict):
            sm = snap.get("safe_mode")
            return sm if isinstance(sm, dict) else {}

        # 2) Иначе best-effort тянем напрямую из UIAPI
        api = getattr(app, "_uiapi", None)
        if api is not None:
            try:
                snap2 = api.get_state_snapshot()
                if isinstance(snap2, dict):
                    sm = snap2.get("safe_mode")
                    return sm if isinstance(sm, dict) else {}
            except Exception:
                pass

        return {}

    def safe_is_on(self) -> bool:
        """SAFE активен, если core сказал safe_mode.active=True."""
        try:
            sm = self._get_safe_snapshot()
            return bool(sm.get("active", False))
        except Exception:
            return False

    def lock_is_on(self) -> bool:
        """LOCK активен, если core сообщил safe_mode.meta.safe_lock_on=True."""
        try:
            sm = self._get_safe_snapshot()
            if not isinstance(sm, dict):
                return False
            meta = sm.get("meta")
            if not isinstance(meta, dict):
                return False
            return bool(meta.get("safe_lock_on", False))
        except Exception:
            return False

    def _policy_denies(self, action: str) -> bool:
        """
        Простая проверка policy deny list.
        Мы считаем действие запрещённым, если deny_actions содержит:
          - exact action (например REAL_BUY)
          - либо REAL_ANY_ORDER как общий запрет
        """
        try:
            sm = self._get_safe_snapshot()
            pol = sm.get("policy") if isinstance(sm, dict) else None
            if not isinstance(pol, dict):
                return False

            deny = pol.get("deny_actions")
            if not isinstance(deny, list):
                return False

            a = str(action or "")
            return ("REAL_ANY_ORDER" in deny) or (a in deny)
        except Exception:
            return False

    def refresh_safe_badge(self) -> None:
        """Обновляет SAFE-бейдж и блокировку REAL действий по policy."""
        app = self.app

        sm = self._get_safe_snapshot()
        active = False
        try:
            active = bool(sm.get("active", False))
        except Exception:
            active = False

        app.safe_on = active

        if active:
            app.badge_safe.configure(text="SAFE", style="BadgeSafe.TLabel")
        else:
            app.badge_safe.configure(text="SAFE OFF", style="BadgeDanger.TLabel")

        # SAFE policy: блокируем REAL ордера (BUY/CLOSE) если запрещено
        mode = getattr(app, "_mode", "SIM")
        lock_on = self.lock_is_on()
        if mode == "REAL":
            # UX: при LOCK любые REAL действия должны выглядеть запрещёнными,
            # даже если deny_actions по какой-то причине пустой.
            deny_any = self._policy_denies("REAL_ANY_ORDER") or lock_on
            deny_buy = deny_any or self._policy_denies("REAL_BUY")
            deny_close = deny_any or self._policy_denies("REAL_CLOSE")

            try:
                app.btn_buy.configure(state="disabled" if deny_buy else "normal")
            except Exception:
                pass

            try:
                app.btn_close.configure(state="disabled" if deny_close else "normal")
            except Exception:
                pass
        # UX: если мы в SIM и core запрещает REAL (или LOCK), делаем Mode “серым”,
        # но не блокируем SIM-кнопки.
        try:
            if mode == "SIM" and (lock_on or self._policy_denies("REAL_ANY_ORDER")):
                app.btn_mode.configure(state="disabled")
            else:
                app.btn_mode.configure(state="normal")
        except Exception:
            pass

        # В SIM кнопки всегда доступны
        if mode == "SIM":
            try:
                app.btn_buy.configure(state="normal")
            except Exception:
                pass
            try:
                app.btn_close.configure(state="normal")
            except Exception:
                pass

    def toggle_safe(self) -> None:
        """
        SAFE MODE — core-owned.
        В STEP1.4.4 UI не должен включать/выключать SAFE напрямую.
        Поэтому клик по бейджу — informational.
        """
        app = self.app
        try:
            app._log("[SAFE] SAFE_MODE is core-owned; UI toggle disabled (policy-driven)")
        except Exception:
            pass

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

        current = getattr(app, "_mode", "SIM")
        cur_mode = getattr(app, "_mode", "SIM")
        new_mode = "REAL" if cur_mode == "SIM" else "SIM"

        # UX: не даём UI уйти в REAL, если core-policy/LOCK запрещают REAL
        if new_mode == "REAL":
            if self.lock_is_on() or self._policy_denies("REAL_ANY_ORDER"):
                try:
                    app._log("[SAFE][POLICY] cannot switch UI to REAL: denied/LOCK; staying SIM")
                except Exception:
                    pass
                new_mode = "SIM"

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
