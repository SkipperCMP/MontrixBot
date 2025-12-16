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

        # STEP1.4.4: SAFE MODE (core-owned) — только отображение из snapshot
        self._safe_lbl = ttk.Label(
            self._frame,
            text="SAFE: —",
            style="Muted.TLabel",
        )
        self._safe_lbl.pack(side=tk.LEFT, padx=(8, 4), pady=4)

        # служебное состояние SAFE MODE
        self._safe_last_text: str = "SAFE: —"

        # STEP1.4.5+: SAFE LOCK (file-lock, core-reported via safe_mode.meta)
        self._lock_lbl = ttk.Label(
            self._frame,
            text="LOCK: —",
            style="Muted.TLabel",
        )
        self._lock_lbl.pack(side=tk.LEFT, padx=(4, 4), pady=4)
        self._lock_last_text: str = "LOCK: —"
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

        # STEP1.4.2: stall overlay (heartbeat watchdog)
        self._stall: bool = False
        self._last_health_style: str = "BadgeSafe.TLabel"
        self._last_health_text: str = "OK"

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

    # алиасы для совместимости с разными подписчиками/проектными ветками
    def set_lag_s(self, seconds: float | int | None) -> None:
        self.set_lag(seconds)

    def set_lag_seconds(self, seconds: float | int | None) -> None:
        self.set_lag(seconds)

    def update_lag(self, seconds: float | int | None) -> None:
        """Старое имя метода для обратной совместимости."""
        self.set_lag(seconds)

    def set_stall(self, is_stall: bool) -> None:
        """
        Принудительный индикатор STALL (нет снапшотов/тик-потока).
        При stall=True бейдж становится красным 'STALL' и не затирается set_health().
        """
        self._stall = bool(is_stall)

        try:
            if self._stall:
                self._health_lbl.configure(text="STALL", style="BadgeDanger.TLabel")
            else:
                # вернуть последний health
                self._health_lbl.configure(text=self._last_health_text, style=self._last_health_style)
        except tk.TclError:
            return

    # ------------ SAFE MODE -------------------------------------------

    def set_safe_mode(self, safe_mode: Mapping[str, Any] | bool | None) -> None:
        """
        Отображает SAFE MODE (core-owned) по snapshot["safe_mode"].

        Поддерживаем форматы:
          - bool
          - dict: {
                "active": bool,
                "reason": str,
                "since_ts": float|int,   # optional
                "severity": "WARN"|"CRIT"|... # optional
            }
        """
        active = False
        reason = ""
        since_ts = None
        severity = ""

        if isinstance(safe_mode, Mapping):
            try:
                active = bool(safe_mode.get("active"))
            except Exception:
                active = False
            try:
                reason = str(safe_mode.get("reason") or "")
            except Exception:
                reason = ""
            try:
                since_ts = safe_mode.get("since_ts")
            except Exception:
                since_ts = None
            try:
                severity = str(safe_mode.get("severity") or "")
            except Exception:
                severity = ""
        elif isinstance(safe_mode, bool):
            active = safe_mode

        age_s: float | None = None
        if since_ts is not None:
            try:
                age_s = max(0.0, time.time() - float(since_ts))
            except Exception:
                age_s = None

        if active:
            # короткая строка для UI
            parts: list[str] = ["SAFE ON"]
            if severity:
                parts.append(severity.upper())
            if reason:
                # не раздуваем строку
                r = reason.strip()
                if len(r) > 32:
                    r = r[:32] + "…"
                parts.append(r)
            if age_s is not None:
                parts.append(f"{age_s:.0f}s")
            text = "SAFE: " + " | ".join(parts)
            style = "BadgeDanger.TLabel"
        else:
            text = "SAFE: OFF"
            style = "Muted.TLabel"

        self._safe_last_text = text
        try:
            self._safe_lbl.configure(text=text, style=style)
        except tk.TclError:
            return

    # ------------ SAFE LOCK -------------------------------------------

    def set_safe_lock(self, lock_on: bool | None, err: str = "") -> None:
        """
        Отображает статус hard-lock (file SAFE_MODE), полученный из snapshot safe_mode.meta.

        lock_on:
          - True  -> LOCK: ON
          - False -> LOCK: OFF
          - None  -> LOCK: —
        err:
          - если не пусто -> LOCK: ERR
        """
        if err:
            text = "LOCK: ERR"
            style = "BadgeDanger.TLabel"
        else:
            if lock_on is True:
                text = "LOCK: ON"
                style = "BadgeWarn.TLabel"
            elif lock_on is False:
                text = "LOCK: OFF"
                style = "Muted.TLabel"
            else:
                text = "LOCK: —"
                style = "Muted.TLabel"

        self._lock_last_text = text
        try:
            self._lock_lbl.configure(text=text, style=style)
        except tk.TclError:
            return

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

        # запоминаем последнее нормальное состояние health
        self._last_health_style = style
        self._last_health_text = text

        # если активен STALL — не перетираем бейдж
        if self._stall:
            return

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
        # mode (если прокинут в snapshot)
        try:
            mode = snapshot.get("mode")
            if mode:
                self.set_mode(str(mode))
        except Exception:
            pass
        health: dict[str, Any] = {}

        # health-блок
        raw_health = snapshot.get("health")
        if isinstance(raw_health, Mapping):
            health = dict(raw_health)

        # STEP1.4.2: приоритет UI-heartbeat из snapshot (ui_lag_s), затем старый механизм health.ts/latency_ms
        lag_sec: float = 0.0
        try:
            ui_lag = snapshot.get("ui_lag_s")
            if ui_lag is None:
                ui_lag = snapshot.get("_ui_lag_s")

            if ui_lag is not None:
                lag_sec = max(0.0, float(ui_lag))
            else:
                latency_ms = health.get("latency_ms")
                if latency_ms is not None:
                    lag_sec = max(0.0, float(latency_ms) / 1000.0)
                else:
                    ts = snapshot.get("ts")
                    if ts is not None:
                        try:
                            ts_f = float(ts)
                        except Exception:
                            ts_f = time.time()
                        lag_sec = max(0.0, time.time() - ts_f)
        except Exception:
            lag_sec = 0.0

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

        # stall (если прокинут в snapshot)
        try:
            if "ui_stall" in snapshot:
                self.set_stall(bool(snapshot.get("ui_stall")))
        except Exception:
            pass

        # STEP1.4.4: SAFE MODE (если прокинут в snapshot)
        # STEP1.4.5+: SAFE LOCK status (safe_mode.meta.safe_lock_on)
        try:
            if "safe_mode" in snapshot:
                sm = snapshot.get("safe_mode")
                self.set_safe_mode(sm)

                lock_on = None
                lock_err = ""
                if isinstance(sm, Mapping):
                    meta = sm.get("meta")
                    if isinstance(meta, Mapping):
                        # может быть True/False/None
                        lock_on = meta.get("safe_lock_on")
                        # строка ошибки (если есть)
                        lock_err = str(meta.get("safe_lock_error") or "")

                self.set_safe_lock(lock_on if isinstance(lock_on, bool) else None, lock_err)
        except Exception:
            pass

        try:
            self.set_health(health)
        except Exception:
            pass

        try:
            self.set_last_deal(last_deal)
        except Exception:
            # не ломаем UI при странном формате снапшота
            pass
