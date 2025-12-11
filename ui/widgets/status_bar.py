from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk
from typing import Any, Mapping, Sequence

from tools.formatting import fmt_price, fmt_pnl


class StatusBar:
    """
    Простой статус-бар (health / lag / mode / last deal).

    Публичный интерфейс (новый API):
    - .frame                   — корневой фрейм
    - set_mode(mode)           — обновить SIM/REAL
    - set_lag(seconds)         — обновить лаг (heartbeat в секундах)
    - set_health(health_dict)  — обновить health-бейдж
    - set_last_deal(deal)      — показать последнюю сделку

    Обратная совместимость:
    - update_lag(seconds)      → set_lag(...)
    - update_last_deal(deal)   → set_last_deal(...)
    """

    def __init__(self, parent: tk.Misc):
        self._frame = ttk.Frame(parent, style="Dark.TFrame")

        # left cluster: HEALTH + LAG + MODE
        # health-бейдж использует общую палитру:
        #   BadgeSafe.TLabel   — зелёный  (OK)
        #   BadgeWarn.TLabel   — жёлтый   (WARN)
        #   BadgeDanger.TLabel — красный  (ERR)
        self._health_lbl = ttk.Label(
            self._frame,
            text="OK",
            style="BadgeSafe.TLabel",
        )
        self._health_lbl.pack(side=tk.LEFT, padx=(8, 4), pady=4)

        self._lag_lbl = ttk.Label(
            self._frame,
            text="lag: 0.0s",
            style="Dark.TLabel",
        )
        self._lag_lbl.pack(side=tk.LEFT, padx=4, pady=4)

        self._mode_lbl = ttk.Label(
            self._frame,
            text="mode: SIM",
            style="Dark.TLabel",
        )
        self._mode_lbl.pack(side=tk.LEFT, padx=4, pady=4)

        ttk.Separator(self._frame, orient="vertical").pack(
            side=tk.LEFT,
            fill=tk.Y,
            padx=8,
            pady=2,
        )

        # right cluster: последняя сделка (symbol, tier, pnl% / pnl$)
        right = ttk.Frame(self._frame, style="Dark.TFrame")
        right.pack(side=tk.RIGHT, padx=8, pady=2)

        self._last_sym = ttk.Label(right, text="—", style="Dark.TLabel")
        self._last_sym.pack(side=tk.LEFT, padx=(0, 4))

        self._last_tier = ttk.Label(right, text="Tier—", style="Muted.TLabel")
        self._last_tier.pack(side=tk.LEFT, padx=(0, 8))

        self._last_pnl_pct = ttk.Label(right, text="—%", style="Dark.TLabel")
        self._last_pnl_pct.pack(side=tk.LEFT, padx=(0, 4))

        self._last_pnl_abs = ttk.Label(right, text="$—", style="Dark.TLabel")
        self._last_pnl_abs.pack(side=tk.LEFT, padx=(0, 4))

        # служебное состояние
        self._last_deal_text: str | None = None
        self._health_status: str = "OK"
        self._health_messages: list[str] = []
        self._last_lag_sec: float = 0.0

    # ------------------------------------------------------------------ properties

    @property
    def frame(self) -> ttk.Frame:
        return self._frame

    # ------------------------------------------------------------------ public API

    def set_mode(self, mode: str) -> None:
        mode = (mode or "SIM").upper()
        try:
            self._mode_lbl.configure(text=f"mode: {mode}")
        except tk.TclError:
            # не даём упасть всему UI из-за статуса
            return

    # ------------ LAG / HEARTBEAT -------------------------------------

    def set_lag(self, seconds: float | int | None) -> None:
        """Обновляет отображение лага и его визуальный уровень."""
        try:
            sec = float(seconds) if seconds is not None else 0.0
        except Exception:
            sec = 0.0

        if sec < 0:
            sec = 0.0

        self._last_lag_sec = sec
        txt = f"lag: {sec:.1f}s"

        # простая градация по порогам:
        #   <= 2s   — зелёный (норма)
        #   2–15s   — жёлтый (предупреждение)
        #   > 15s   — красный (проблемы с потоком тиков)
        try:
            if sec <= 2.0:
                fg = "#a6f3a6"   # мягкий зелёный
            elif sec <= 15.0:
                fg = "#ffd866"   # тёплый жёлтый
            else:
                fg = "#ff6b6b"   # красный

            self._lag_lbl.configure(text=txt, foreground=fg)
        except tk.TclError:
            return

    def update_lag(self, seconds: float | int | None) -> None:
        """Старое имя метода для обратной совместимости."""
        self.set_lag(seconds)

    # ------------ HEALTH ----------------------------------------------

    def set_health(self, health: Mapping[str, Any] | None) -> None:
        """
        Обновляет health-бейдж по данным из snapshot["health"].

        Ожидаемый формат health:
            {
                "status": "OK" | "WARN" | "ERROR" | ...,
                "messages": [ ... ]  # опционально
                "latency_ms": float   # опционально, уже учтён в lag
                ...
            }
        """
        health = dict(health or {})
        status_raw = health.get("status") or "OK"
        status = str(status_raw).upper()

        messages = health.get("messages") or []
        if isinstance(messages, (str, bytes)):
            messages = [messages]
        elif not isinstance(messages, Sequence):
            messages = [str(messages)]

        self._health_status = status
        self._health_messages = [str(m) for m in messages if m]

        # Маппинг статус → стиль бейджа
        if status in ("OK", "GOOD"):
            style = "BadgeSafe.TLabel"
            text = "OK"
        elif status in ("WARN", "WARNING"):
            style = "BadgeWarn.TLabel"
            text = "WARN"
        elif status in ("ERROR", "ERR", "CRIT", "CRITICAL"):
            style = "BadgeDanger.TLabel"
            text = "ERR"
        else:
            # неизвестный статус считаем «предупреждением»
            style = "BadgeWarn.TLabel"
            text = status[:6] or "STATE"

        try:
            self._health_lbl.configure(text=text, style=style)
        except tk.TclError:
            return

    # ------------ LAST DEAL -------------------------------------------

    def set_last_deal(self, deal: Mapping[str, Any] | None) -> None:
        """Отображает последнюю сделку в правом кластере статус-бара."""
        if not deal:
            # сброс до дефолта
            self._last_deal_text = None
            try:
                self._last_sym.configure(text="—")
                self._last_tier.configure(text="Tier—")
                self._last_pnl_pct.configure(text="—%")
                self._last_pnl_abs.configure(text="$—")
            except tk.TclError:
                pass
            return

        sym = deal.get("symbol") or deal.get("sym") or "—"
        tier = deal.get("tier")
        pnl_pct = deal.get("pnl_pct")
        # поддерживаем и pnl_abs, и просто pnl
        pnl_abs = deal.get("pnl_abs")
        if pnl_abs is None:
            pnl_abs = deal.get("pnl")

        try:
            self._last_sym.configure(text=str(sym))
            self._last_tier.configure(
                text=f"Tier{tier if tier is not None else '—'}"
            )
            self._last_pnl_pct.configure(
                text=f"{fmt_pnl(pnl_pct)}% " if pnl_pct is not None else "—%"
            )
            self._last_pnl_abs.configure(
                text=f"${fmt_price(pnl_abs)}" if pnl_abs is not None else "$—"
            )
        except tk.TclError:
            # не даём упасть всему UI из-за статуса
            return

    def update_last_deal(self, deal: Mapping[str, Any] | None) -> None:
        """Старое имя метода для обратной совместимости."""
        self.set_last_deal(deal)

    def update_from_snapshot(self, snapshot: Mapping[str, Any] | None) -> None:
        """
        Обновляет health / lag / last deal по снапшоту StateEngine.

        Ожидаемый формат snapshot:
        {
            "ts": <timestamp>,
            "health": {
                "latency_ms": <опционально>,
                ...
            },
            "trades_recent": [ {...}, {...}, ... ]
        }
        """
        snapshot = snapshot or {}
        health: dict[str, Any] = {}

        # health-блок
        raw_health = snapshot.get("health")
        if isinstance(raw_health, Mapping):
            health = dict(raw_health)

        # lag по health.latency_ms или по ts снапшота
        lag_sec = 0
        try:
            latency_ms = health.get("latency_ms")
            if latency_ms is not None:
                lag_sec = max(0, int(float(latency_ms) / 1000.0))
            else:
                ts = snapshot.get("ts")
                if ts is not None:
                    try:
                        ts_f = float(ts)
                    except Exception:
                        ts_f = time.time()
                    lag_sec = max(0, int(time.time() - ts_f))
        except Exception:
            lag_sec = 0

        # применяем lag в статус-бар
        try:
            self.set_lag(lag_sec)
        except Exception:
            # проблемы с лагом не должны ронять UI
            pass

        # последняя сделка
        last_deal = None
        rows = snapshot.get("trades_recent")
        if isinstance(rows, Sequence) and rows:
            last_deal = rows[-1]

        try:
            self.set_health(health)
        except Exception:
            pass

        try:
            self.set_last_deal(last_deal)
        except Exception:
            # не ломаем UI при странном формате снапшота
            pass
