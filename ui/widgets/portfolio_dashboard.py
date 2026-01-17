from __future__ import annotations

"""ui/widgets/portfolio_dashboard.py

Portfolio Dashboard (read-only).

v2.3.2 scope:
 - Portfolio headline metrics (equity, PnL, open positions)
 - Equity / PnL% chart with range selector (1h/24h/7d/all)
 - Cold-start preload from runtime/equity_history.csv (read-only)
 - STALE/Safe freeze: do not append new points when snapshot is stalled/safe
 - Updates ONLY from EVT_SNAPSHOT (no polling, no side-effects)

IMPORTANT:
 - UI remains read-only (no runtime writes).
 - This widget is passive and receives data through the EventBus.
"""

from dataclasses import dataclass
from typing import Any, Deque, Optional
from collections import deque

import time
import tkinter as tk
from tkinter import ttk

from tools.formatting import fmt_price, fmt_pnl
from tools.ipc_equity import read_equity_history


# ---------------------------------------------------------------------------
# Optional matplotlib backend (preferred)
# ---------------------------------------------------------------------------

_HAS_MPL = False
FigureCanvasTkAgg = None
Figure = None

try:
    import matplotlib

    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg as _FCTA
    from matplotlib.figure import Figure as _Fig

    FigureCanvasTkAgg = _FCTA
    Figure = _Fig
    _HAS_MPL = True
except Exception:
    _HAS_MPL = False


@dataclass
class _Point:
    ts: float
    equity: float


class PortfolioDashboard:
    """Read-only portfolio dashboard.

    Public API:
      - .frame
      - .update_from_snapshot(snapshot: dict)
    """

    def __init__(self, parent: tk.Misc) -> None:
        self._frame = ttk.Frame(parent, style="Dark.TFrame")

        # headline row
        head = ttk.Frame(self._frame, style="Dark.TFrame")
        head.pack(fill="x", padx=8, pady=(8, 6))

        self._lbl_title = ttk.Label(head, text="Portfolio Dashboard", style="Muted.TLabel")
        self._lbl_title.pack(side=tk.LEFT)

        # v2.3.2 — chart mode + range selectors
        self._metric_var = tk.StringVar(value="Equity")
        self._range_var = tk.StringVar(value="24h")

        try:
            metric_cb = ttk.Combobox(
                head,
                textvariable=self._metric_var,
                values=["Equity", "PnL%"],
                width=8,
                state="readonly",
            )
            metric_cb.pack(side=tk.LEFT, padx=(12, 6))
            metric_cb.bind("<<ComboboxSelected>>", lambda _e: self._redraw())
        except Exception:
            pass

        try:
            range_cb = ttk.Combobox(
                head,
                textvariable=self._range_var,
                values=["1h", "24h", "7d", "all"],
                width=6,
                state="readonly",
            )
            range_cb.pack(side=tk.LEFT, padx=(0, 6))
            range_cb.bind("<<ComboboxSelected>>", lambda _e: self._redraw())
        except Exception:
            pass

        self._lbl_age = ttk.Label(head, text="", style="Muted.TLabel")
        self._lbl_age.pack(side=tk.RIGHT)

        # metrics row
        metrics = ttk.Frame(self._frame, style="Dark.TFrame")
        metrics.pack(fill="x", padx=8, pady=(0, 8))

        self._lbl_equity = ttk.Label(metrics, text="Equity: $—", style="Dark.TLabel")
        self._lbl_equity.pack(side=tk.LEFT, padx=(0, 14))

        self._lbl_day = ttk.Label(metrics, text="Day: —%", style="Dark.TLabel")
        self._lbl_day.pack(side=tk.LEFT, padx=(0, 14))

        self._lbl_total = ttk.Label(metrics, text="Total: —%", style="Dark.TLabel")
        self._lbl_total.pack(side=tk.LEFT, padx=(0, 14))

        self._lbl_open = ttk.Label(metrics, text="Open: 0", style="Dark.TLabel")
        self._lbl_open.pack(side=tk.LEFT, padx=(0, 14))

        self._lbl_mode = ttk.Label(metrics, text="Mode: —", style="Muted.TLabel")
        self._lbl_mode.pack(side=tk.RIGHT)

        # chart container
        chart_box = ttk.Frame(self._frame, style="Dark.TFrame")
        chart_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._chart_box = chart_box
        self._canvas = None
        self._mpl_canvas = None
        self._mpl_fig = None
        self._mpl_ax = None

        # time series (equity points)
        self._series: Deque[_Point] = deque(maxlen=800)
        self._last_point_ts: Optional[float] = None
        self._freeze_stale: bool = False

        # build chart
        if _HAS_MPL and FigureCanvasTkAgg is not None and Figure is not None:
            self._build_mpl_chart()
        else:
            self._build_tk_chart()

        # v2.3.2 — preload history (read-only)
        self._preload_history()

        self._last_snapshot_ts: Optional[float] = None

    @property
    def frame(self) -> ttk.Frame:
        return self._frame

    def _build_mpl_chart(self) -> None:
        assert Figure is not None and FigureCanvasTkAgg is not None

        fig = Figure(figsize=(6, 3), dpi=100)
        ax = fig.add_subplot(111)
        ax.set_title("Equity", fontsize=10)
        ax.grid(True, alpha=0.25)

        canvas = FigureCanvasTkAgg(fig, master=self._chart_box)
        widget = canvas.get_tk_widget()
        widget.pack(fill="both", expand=True)

        self._mpl_fig = fig
        self._mpl_ax = ax
        self._mpl_canvas = canvas

    def _build_tk_chart(self) -> None:
        c = tk.Canvas(self._chart_box, highlightthickness=0)
        c.pack(fill="both", expand=True)
        self._canvas = c
        c.bind("<Configure>", lambda _e: self._draw_tk())

    def update_from_snapshot(self, snapshot: dict) -> None:
        if not isinstance(snapshot, dict):
            return

        # v2.3.3 — Data Contract Bridge (read-only)
        # Snapshot contracts can vary by version. We try several safe locations.
        def _pick(*paths: str) -> Any:
            for p in paths:
                cur: Any = snapshot
                ok = True
                for part in p.split("."):
                    if isinstance(cur, dict) and part in cur:
                        cur = cur.get(part)
                    else:
                        ok = False
                        break
                if ok:
                    return cur
            return None

        portfolio = _pick("portfolio") if isinstance(_pick("portfolio"), dict) else {}

        eq = _pick("portfolio.equity", "equity", "sim_state.equity", "state.equity")
        day = _pick("portfolio.pnl_day_pct", "pnl_day_pct", "sim_state.pnl_day_pct", "state.pnl_day_pct")
        total = _pick("portfolio.pnl_total_pct", "pnl_total_pct", "sim_state.pnl_total_pct", "state.pnl_total_pct")
        open_cnt = _pick("portfolio.open_positions_count", "open_positions_count", "sim_state.open_positions_count", "state.open_positions_count")
        open_pnl_abs = _pick("portfolio.open_pnl_abs", "open_pnl_abs", "sim_state.open_pnl_abs", "state.open_pnl_abs")
        mode = _pick("mode") or "—"

        try:
            if eq is None:
                self._lbl_equity.configure(text="Equity: $—")
            else:
                self._lbl_equity.configure(text=f"Equity: ${fmt_price(eq)}")
        except Exception:
            pass

        def _fmt_pct(v: Any) -> str:
            if v is None:
                return "—%"
            try:
                return f"{fmt_pnl(float(v))}%"
            except Exception:
                return "—%"

        try:
            self._lbl_day.configure(text=f"Day: {_fmt_pct(day)}")
        except Exception:
            pass
        try:
            self._lbl_total.configure(text=f"Total: {_fmt_pct(total)}")
        except Exception:
            pass

        try:
            cnt = int(open_cnt) if open_cnt is not None else 0
        except Exception:
            cnt = 0

        try:
            if open_pnl_abs is None:
                self._lbl_open.configure(text=f"Open: {cnt}")
            else:
                self._lbl_open.configure(text=f"Open: {cnt} ({fmt_pnl(open_pnl_abs)}$)")
        except Exception:
            pass

        try:
            self._lbl_mode.configure(text=f"Mode: {mode}")
        except Exception:
            pass

        age_s = None
        try:
            age_s = snapshot.get("ui_lag_s")
            age_s = float(age_s) if age_s is not None else None
        except Exception:
            age_s = None

        # If ui_lag_s is absent, derive age from snapshot timestamp if available.
        if age_s is None:
            snap_ts = None
            try:
                snap_ts = snapshot.get("snapshot_ts") or snapshot.get("snapshot_time") or snapshot.get("ts")
                snap_ts = float(snap_ts) if snap_ts is not None else None
            except Exception:
                snap_ts = None
            if snap_ts is not None and snap_ts > 0:
                age_s = max(0.0, time.time() - snap_ts)

        # Fallback: derive from last_tick_ts (legacy)
        if age_s is None:
            try:
                last_ts = snapshot.get("last_tick_ts")
                last_ts = float(last_ts) if last_ts is not None else None
                if last_ts is not None and last_ts > 0:
                    age_s = max(0.0, time.time() - last_ts)
            except Exception:
                age_s = None

        # stale / freeze logic (v2.3.2)
        stale = False
        try:
            if snapshot.get("ui_stall") is True:
                stale = True
        except Exception:
            pass
        try:
            # SAFE MODE in snapshot is also a strong signal
            if snapshot.get("safe_mode") is True:
                stale = True
        except Exception:
            pass

        self._freeze_stale = bool(stale)

        try:
            if age_s is None:
                self._lbl_age.configure(text="")
            else:
                tail = " (STALE)" if stale else ""
                self._lbl_age.configure(text=f"snapshot age: {age_s:.1f}s{tail}")
        except Exception:
            pass

        # Append point ONLY when not stale/frozen
        try:
            if (not self._freeze_stale) and (eq is not None):
                ts = float(snapshot.get("last_tick_ts") or time.time())
                if self._last_point_ts is None or abs(ts - self._last_point_ts) >= 0.001:
                    self._series.append(_Point(ts=ts, equity=float(eq)))
                    self._last_point_ts = ts
        except Exception:
            pass

        self._redraw()

    def _preload_history(self) -> None:
        """Load equity history from runtime/equity_history.csv (read-only)."""
        try:
            rows = read_equity_history(max_points=800)
        except Exception:
            rows = []
        if not rows:
            return
        try:
            for ts, eq in rows:
                if ts and eq is not None:
                    self._series.append(_Point(ts=float(ts), equity=float(eq)))
            if self._series:
                self._last_point_ts = self._series[-1].ts
        except Exception:
            return

    def _get_view_points(self) -> list[_Point]:
        pts = list(self._series)
        if not pts:
            return pts
        rng = (self._range_var.get() or "all").lower()
        if rng == "all":
            return pts

        now_ts = pts[-1].ts
        window_s = None
        if rng == "1h":
            window_s = 3600.0
        elif rng == "24h":
            window_s = 24.0 * 3600.0
        elif rng == "7d":
            window_s = 7.0 * 24.0 * 3600.0

        if window_s is None:
            return pts
        cutoff = now_ts - window_s
        return [p for p in pts if p.ts >= cutoff]

    def _series_for_metric(self, pts: list[_Point]) -> tuple[list[float], list[float], str]:
        """Return xs, ys, title."""
        xs = [p.ts for p in pts]
        metric = (self._metric_var.get() or "Equity").strip()
        if metric == "PnL%":
            base = pts[0].equity if pts else 0.0
            if base <= 0:
                ys = [0.0 for _p in pts]
            else:
                ys = [((p.equity / base) - 1.0) * 100.0 for p in pts]
            return xs, ys, "PnL%"

        ys = [p.equity for p in pts]
        return xs, ys, "Equity"

    def _redraw(self) -> None:
        try:
            if self._mpl_canvas is not None:
                self._draw_mpl()
            else:
                self._draw_tk()
        except Exception:
            pass

    def _draw_mpl(self) -> None:
        if self._mpl_ax is None or self._mpl_canvas is None:
            return

        pts = self._get_view_points()
        xs, ys, title = self._series_for_metric(pts)

        ax = self._mpl_ax
        ax.clear()
        ax.set_title(title, fontsize=10)
        ax.grid(True, alpha=0.25)

        if len(xs) >= 2:
            ax.plot(xs, ys, linewidth=1.5)
        else:
            ax.text(0.5, 0.5, "waiting for data...", transform=ax.transAxes, ha="center", va="center")

        ax.set_xticks([])
        self._mpl_canvas.draw_idle()

    def _draw_tk(self) -> None:
        c = self._canvas
        if c is None:
            return
        c.delete("all")

        w = int(c.winfo_width() or 1)
        h = int(c.winfo_height() or 1)

        pts = self._get_view_points()
        if len(pts) < 2:
            c.create_text(w // 2, h // 2, text="waiting for data...", fill="#bbbbbb", font=("Segoe UI", 12))
            return

        xs, ys, title = self._series_for_metric(pts)
        min_y = min(ys)
        max_y = max(ys)
        if max_y <= min_y:
            max_y = min_y + 1.0

        pad = 10
        x0, y0 = pad, pad
        x1, y1 = w - pad, h - pad

        n = len(ys)
        pts = []
        for i, y in enumerate(ys):
            x = x0 + (x1 - x0) * (i / max(1, n - 1))
            yy = y1 - (y - min_y) / (max_y - min_y) * (y1 - y0)
            pts.extend([x, yy])

        c.create_line(*pts, width=2, fill="#4aa3ff")
        if title == "PnL%":
            tail = f"{fmt_pnl(ys[-1])}%"
        else:
            tail = f"{fmt_price(ys[-1])}$"
        c.create_text(pad, pad, anchor="nw", text=tail, fill="#e6e6e6", font=("Segoe UI", 10, "bold"))
