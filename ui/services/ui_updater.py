from __future__ import annotations

import time

from typing import Any

from ui.strategy_contract import get_ui_activity_throttle_sec


class UIRefreshService:
    """Периодический рефреш UI (SAFE, Dry-Run, индикаторы, snapshot).

    Сервис работает на уровне UI-слоя и знает только про объект App.
    Вся логика остаётся на стороне App (через его методы), но цикл
    и обработка ошибок сосредоточены здесь.

    Это первый шаг к Unified Refresh Loop (STEP1.3.3).
    """

    def __init__(self, app: Any, interval_ms: int = 1000) -> None:
        self.app = app
        self.interval_ms = interval_ms
        self._running = False

        # Throttle for Strategy Activity Badge refresh (seconds).
        # UI-only, read-only: reduces churn if the main refresh interval is small.
        try:
            self._activity_throttle_sec = float(get_ui_activity_throttle_sec() or 0.0)
        except Exception:
            self._activity_throttle_sec = 0.0
        self._last_activity_refresh_m = 0.0

    # ------------------------------------------------------------------ API

    def start(self) -> None:
        """Запускает периодический цикл обновления UI."""
        if self._running:
            return
        self._running = True
        self._schedule_next_tick()

    def stop(self) -> None:
        """Останавливает цикл обновления UI."""
        self._running = False

    # ----------------------------------------------------------------- internals

    def _schedule_next_tick(self) -> None:
        """Планирует следующий вызов periodic_refresh через .after()."""
        if not self._running:
            return

        try:
            self.app.after(self.interval_ms, self.periodic_refresh)
        except Exception:
            # если .after() внезапно не сработал — останавливаемся,
            # чтобы не уйти в неконтролируемый цикл
            self._running = False

    def periodic_refresh(self) -> None:
        """Периодический апдейт SAFE, Dry-Run, индикаторов и мини-панелей."""
        if not self._running:
            # на всякий случай выходим, если нас остановили между тиками
            return

        app = self.app

        try:
            # SAFE-индикатор
            app._refresh_safe_badge()

            # Dry-Run бейдж (пока чисто UI)
            app._refresh_dry_badge()

            # индикаторы + сигналы + AUTOSIM
            app._refresh_indicators_and_signal()

            # синхронизируем текущий символ в ядро (UIAPI)
            app._push_current_symbol_to_uiapi()

            # подтягиваем снапшот из StateEngine/UIAPI
            # и обновляем мини-equity + статус-бар + журнал
            app._refresh_from_core_snapshot()

            # Strategy Registry: activity badges (UI-only)
            if hasattr(app, "_refresh_strategy_activity_badges"):
                if self._activity_throttle_sec > 0.0:
                    try:
                        now_m = time.monotonic()
                        if (now_m - self._last_activity_refresh_m) >= self._activity_throttle_sec:
                            self._last_activity_refresh_m = now_m
                            app._refresh_strategy_activity_badges()
                    except Exception:
                        # be conservative: if throttle logic fails, skip this tick
                        pass
                else:
                    app._refresh_strategy_activity_badges()
        except Exception as e:  # noqa: BLE001
            # повторяем существующее поведение App._periodic_refresh:
            # логируем ошибку, но не убиваем цикл целиком.
            try:
                app._log(f"[DIAG] periodic error: {e!r}")
            except Exception:
                pass
        finally:
            self._schedule_next_tick()
