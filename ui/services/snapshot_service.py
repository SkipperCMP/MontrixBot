from __future__ import annotations

from typing import Any


class SnapshotService:
    """Обновление мини-панелей по снапшоту ядра (UIAPI/StateEngine).

    Сюда вынесена логика из App._refresh_from_core_snapshot:
    - получение snapshot из UIAPI;
    - обновление mini-equity / status-bar;
    - обновление окна deals journal.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    def refresh_from_core_snapshot(self) -> None:
        """Запрашивает snapshot у UIAPI и обновляет связанные панели.

        Любые ошибки внутри метода не должны ломать основной UI:
        все блоки обёрнуты в try/except (best-effort).
        """
        app = self.app

        # 1) получаем снапшот из UIAPI / StateEngine
        try:
            api = app._ensure_uiapi()
            if api is None or not hasattr(api, "get_state_snapshot"):
                return

            snapshot = api.get_state_snapshot()
            if not isinstance(snapshot, dict):
                return

            # 1b) runtime persistence hook (через UIAPI)
            try:
                if hasattr(api, "maybe_persist_runtime_state"):
                    api.maybe_persist_runtime_state(snapshot)
            except Exception:
                # проблемы сохранения runtime не должны ломать UI
                pass
        except Exception:
            return

        # 2) статус-бар и mini-equity (если доступны в App)
        try:
            app._update_status_bar(snapshot)
        except Exception:
            pass

        # 3) TickService / Update Router — tick-чувствительные элементы UI
        try:
            tu = getattr(app, "tick_updater", None)
            if tu is not None and hasattr(tu, "update_from_snapshot"):
                tu.update_from_snapshot(snapshot)
        except Exception:
            # любые проблемы тик-сервиса не должны ломать основной UI
            pass

        # 4) журнал сделок (если зарегистрирован)
        try:
            dj = getattr(app, "_deals_journal_widget", None)
            if dj is not None and hasattr(dj, "update_from_snapshot"):
                dj.update_from_snapshot(snapshot)
        except Exception:
            # ошибки обновления журнала не должны ломать основной UI
            pass
