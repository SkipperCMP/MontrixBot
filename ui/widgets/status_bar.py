
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from tools.formatting import fmt_price, fmt_pnl

class StatusBar:
    def __init__(self, parent: tk.Misc):
        self._frame = ttk.Frame(parent)
        # left cluster: health/mode/lag
        self._ok = ttk.Label(self._frame, text="OK"); self._ok.pack(side=tk.LEFT, padx=(8,4), pady=4)
        self._lag_lbl = ttk.Label(self._frame, text="lag: 0s"); self._lag_lbl.pack(side=tk.LEFT, padx=4, pady=4)
        self._mode_lbl = ttk.Label(self._frame, text="mode: SIM"); self._mode_lbl.pack(side=tk.LEFT, padx=4, pady=4)
        # separator
        ttk.Separator(self._frame, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=2)
        # right cluster: last deal details (symbol, tier, pnl% / pnl$)
        self._last_title = ttk.Label(self._frame, text="LAST:"); self._last_title.pack(side=tk.LEFT, padx=(4,2), pady=4)
        self._last_sym = ttk.Label(self._frame, text="—"); self._last_sym.pack(side=tk.LEFT, padx=2, pady=4)
        self._last_tier = ttk.Label(self._frame, text="Tier—"); self._last_tier.pack(side=tk.LEFT, padx=2, pady=4)
        self._last_pnl_pct = ttk.Label(self._frame, text="—%"); self._last_pnl_pct.pack(side=tk.LEFT, padx=2, pady=4)
        self._last_pnl_abs = ttk.Label(self._frame, text="$—"); self._last_pnl_abs.pack(side=tk.LEFT, padx=2, pady=4)

        self._mode = "SIM"
        self._lag = 0

        # кэш последних текстовых значений, чтобы не дёргать Tk без изменений
        self._last_mode_text: str = ""
        self._last_lag_text: str = ""
        self._last_status_text: str = ""
        self._last_deal_text: str = ""

    @property
    def frame(self):
        return self._frame

    def set_mode(self, mode: str) -> None:
        self._mode = mode or "SIM"
        text = f"mode: {self._mode}"
        # избегаем лишних обновлений, если текст не изменился
        if getattr(self, "_last_mode_text", None) == text:
            return
        self._last_mode_text = text
        self._mode_lbl.configure(text=text)

    def set_lag(self, lag: int) -> None:
        """
        Обновляет задержку ...
        """
        try:
            self._lag = max(0, int(lag))
        except Exception:
            self._lag = 0

        text = f"lag: {self._lag}s"
        # не обновляем label, если текст не изменился
        if getattr(self, "_last_lag_text", None) == text:
            return
        self._last_lag_text = text
        self._lag_lbl.configure(text=text)
        
    def set_health(self, health: dict | None) -> None:
        """
        Обновляет левый индикатор состояния по snapshot['health'].

        Ожидаемый формат health:
            {
                "status": "OK" | "WARN" | "ERROR" | ...,
                "latency_ms": <optional float>,
                "source": <optional str>,
                "messages": <optional list/str>,
                ...
            }
        """
        if health is None:
            health = {}

        # базовый статус из health['status']
        raw_status = str(health.get("status", "OK") or "OK").upper()
        if raw_status in ("OK", "GOOD"):
            status_text = "OK"
        elif raw_status.startswith("WARN"):
            status_text = "WARN"
        else:
            status_text = "ERR"

        # latency_ms -> секунды, если есть
        latency_ms = health.get("latency_ms")
        latency_sec = None
        try:
            if latency_ms is not None:
                latency_ms = float(latency_ms)
                latency_sec = max(0.0, latency_ms / 1000.0)
        except Exception:
            latency_ms = None
            latency_sec = None

        # авто-эскалация по лагу: при больших задержках поднимаем статус
        try:
            if latency_sec is not None:
                if latency_sec >= 15.0 and status_text == "OK":
                    status_text = "ERR"
                elif latency_sec >= 5.0 and status_text == "OK":
                    status_text = "WARN"
        except Exception:
            pass

        # лёгкий текстовый суффикс для latency
        suffix = ""
        if isinstance(latency_sec, (int, float)):
            if latency_sec >= 15.0:
                suffix = " (lag)"
            elif latency_sec >= 5.0:
                suffix = " (slow)"

        # компактный source-маркер: [WS] / [API] / [SNAP] по health.source / messages
        source_tag = ""
        try:
            src = str(health.get("source", "") or "")
            msgs = health.get("messages") or []
            if isinstance(msgs, (str, bytes)):
                msgs_list = [msgs]
            elif isinstance(msgs, (list, tuple, set)):
                msgs_list = list(msgs)
            else:
                msgs_list = []

            blob = (src + " " + " ".join(str(m) for m in msgs_list)).lower()
            if "websocket" in blob or " ws " in blob or blob.startswith("ws"):
                source_tag = " [WS]"
            elif "api" in blob or "rest" in blob:
                source_tag = " [API]"
            elif "snap" in blob or "state" in blob:
                source_tag = " [SNAP]"
        except Exception:
            source_tag = ""

        status_full = f"{status_text}{suffix}{source_tag}"
        # не дёргаем label, если текст полностью совпадает
        if getattr(self, "_last_status_text", None) == status_full:
            return
        self._last_status_text = status_full
        self._ok.configure(text=status_full)

    def set_last_deal(self, deal: dict | None) -> None:
        if not deal:
            # очищаем, но только если состояние действительно изменилось
            key = "__EMPTY__"
            if getattr(self, "_last_deal_text", None) == key:
                return
            self._last_deal_text = key
            self._last_sym.configure(text="—")
            self._last_tier.configure(text="Tier—")
            self._last_pnl_pct.configure(text="—%")
            self._last_pnl_abs.configure(text="$—")
            return

        sym = str(deal.get("symbol", "—"))
        tier = deal.get("tier")
        pnl_pct = deal.get("pnl_pct")
        pnl_abs = deal.get("pnl_abs")

        key = f"{sym}|{tier}|{pnl_pct}|{pnl_abs}"
        # короткая нормализация, чтобы не дёргать label из-за хвостовых пробелов
        key = key.strip()
        if getattr(self, "_last_deal_text", None) == key:
            return
        self._last_deal_text = key

        self._last_sym.configure(text=sym)
        self._last_tier.configure(text=f"Tier{tier if tier is not None else '—'}")
        self._last_pnl_pct.configure(text=f"{fmt_pnl(pnl_pct)}% " if pnl_pct is not None else "—%")
        self._last_pnl_abs.configure(text=f"${fmt_price(pnl_abs)}" if pnl_abs is not None else "$—")

