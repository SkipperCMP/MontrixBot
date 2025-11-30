from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from tools.formatting import fmt_price, fmt_pnl


class StatusBar:
    """Простой статус-бар (health / lag / mode / last deal).

    Публичный интерфейс:
    - .frame               — корневой фрейм
    - set_mode(mode)       — обновить SIM/REAL
    - update_lag(seconds)  — обновить лаг (heartbeat)
    - update_last_deal(d)  — показать последнюю сделку
    """

    def __init__(self, parent: tk.Misc):
        self._frame = ttk.Frame(parent, style="Dark.TFrame")

        # left cluster: health / lag / mode
        self._ok = ttk.Label(self._frame, text="OK", style="Dark.TLabel")
        self._ok.pack(side=tk.LEFT, padx=(8, 4), pady=4)

        self._lag_lbl = ttk.Label(self._frame, text="lag: 0.0s", style="Dark.TLabel")
        self._lag_lbl.pack(side=tk.LEFT, padx=4, pady=4)

        self._mode_lbl = ttk.Label(self._frame, text="mode: SIM", style="Dark.TLabel")
        self._mode_lbl.pack(side=tk.LEFT, padx=4, pady=4)

        ttk.Separator(self._frame, orient="vertical").pack(
            side=tk.LEFT, fill=tk.Y, padx=8, pady=2
        )

        # right cluster: last deal details (symbol, tier, pnl% / pnl$)
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

        self._last_deal_text: str | None = None

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
            pass

    def update_lag(self, seconds: float | int | None) -> None:
        try:
            sec = float(seconds) if seconds is not None else 0.0
        except Exception:
            sec = 0.0
        txt = f"lag: {sec:.1f}s"
        try:
            self._lag_lbl.configure(text=txt)
        except tk.TclError:
            pass

    def update_last_deal(self, deal: dict | None) -> None:
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
        pnl_abs = deal.get("pnl_abs")

        key = f"{sym}|{tier}|{pnl_pct}|{pnl_abs}".strip()
        if self._last_deal_text == key:
            return
        self._last_deal_text = key

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
