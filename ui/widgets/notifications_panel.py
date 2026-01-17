from __future__ import annotations

"""
ui/widgets/notifications_panel.py

MontrixBot v2.3.7 — Telegram Notifications v1.1 (Filters + Dedupe + PnL Digest)

Goals:
- In-UI notifications history (read-only)
- System notifications from EVT_SNAPSHOT (SAFE/STALE/ERROR/TRADE lifecycle)
- Optional Telegram sink (monitoring-only, no control surface)
- Telegram filters by level/category + TTL dedupe
- Optional PnL digest (rate-limited, thresholded)

STRICT INVARIANTS:
- UI must not write runtime state files.
- Telegram sending is optional and must be opt-in via env.
- Telegram is a sink only (no commands, no control surface).
"""

from dataclasses import dataclass
from typing import Any, Deque, Optional, Tuple, Dict
from collections import deque
import os
import time
import hashlib
import urllib.request
import urllib.parse
import tkinter as tk
from tkinter import ttk


# ----------------------------- Config (env) -----------------------------

def _env_bool(name: str, default: str = "0") -> bool:
    v = str(os.environ.get(name, default) or "").strip().lower()
    return v in ("1", "true", "yes", "on")

def _env_float(name: str, default: str) -> float:
    try:
        return float(os.environ.get(name, default) or default)
    except Exception:
        return float(default)

def _env_int(name: str, default: str) -> int:
    try:
        return int(os.environ.get(name, default) or default)
    except Exception:
        return int(default)

def _env_csv_set(name: str, default: str) -> set[str]:
    raw = str(os.environ.get(name, default) or default).strip()
    if not raw:
        return set()
    out = set()
    for p in raw.split(","):
        p = p.strip().upper()
        if p:
            out.add(p)
    return out


TELEGRAM_ENABLED = _env_bool("MONTRIX_TELEGRAM_NOTIFY", "0")
TELEGRAM_TOKEN = str(os.environ.get("TELEGRAM_BOT_TOKEN", "") or "").strip()
TELEGRAM_CHAT_ID = str(os.environ.get("TELEGRAM_CHAT_ID", "") or "").strip()

# hard rate-limit per message send
TG_MIN_INTERVAL_S = _env_float("MONTRIX_TG_MIN_INTERVAL_S", "3")

# dedupe TTL window for telegram messages (seconds)
TG_DEDUPE_TTL_S = _env_float("MONTRIX_TG_DEDUPE_TTL_S", "600")

# telegram filters (CSV, uppercase)
# Example:
#   MONTRIX_TG_LEVELS=WARNING,ERROR
#   MONTRIX_TG_CATEGORIES=SAFE,STALE,ERROR,TRADE,PNL
TG_LEVELS_ALLOW = _env_csv_set("MONTRIX_TG_LEVELS", "WARNING,RISK,ERROR")
TG_CATEGORIES_ALLOW = _env_csv_set("MONTRIX_TG_CATEGORIES", "SAFE,STALE,ERROR,TRADE,PNL")

# Optional PnL digest (telegram) settings:
TG_PNL_DIGEST_ENABLED = _env_bool("MONTRIX_TG_PNL_DIGEST", "1")
TG_PNL_INTERVAL_S = _env_float("MONTRIX_TG_PNL_INTERVAL_S", "300")  # 5 min
TG_PNL_MIN_DELTA_PCT = _env_float("MONTRIX_TG_PNL_MIN_DELTA_PCT", "0.20")  # 0.20% change threshold

# max UI history
MAX_NOTIFS = _env_int("MONTRIX_NOTIFS_MAX", "500")

LEVELS = ("INFO", "WARNING", "RISK", "ERROR")
CATEGORIES = ("SYSTEM", "SAFE", "STALE", "TRADE", "GATE", "ERROR", "PNL")


@dataclass
class Notification:
    ts: float
    level: str
    category: str
    title: str
    message: str
    source: str = "UI"

    def to_row(self) -> Tuple[str, str, str, str, str]:
        t = time.strftime("%H:%M:%S", time.localtime(self.ts))
        return (t, self.level, self.category, self.title, self.message)


# ----------------------------- Telegram sink -----------------------------

class _TelegramSink:
    def __init__(self) -> None:
        self._last_sent_ts: float = 0.0
        # hash -> last_seen_ts (TTL window)
        self._dedupe: Dict[str, float] = {}

    def enabled(self) -> bool:
        return bool(TELEGRAM_ENABLED and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)

    def _gc(self, now: float) -> None:
        if not self._dedupe:
            return
        ttl = max(1.0, TG_DEDUPE_TTL_S)
        dead = [h for h, ts in self._dedupe.items() if now - ts > ttl]
        for h in dead:
            self._dedupe.pop(h, None)

    def allow(self, level: str, category: str) -> bool:
        if not self.enabled():
            return False
        lvl = (level or "INFO").upper()
        cat = (category or "SYSTEM").upper()
        if TG_LEVELS_ALLOW and (lvl not in TG_LEVELS_ALLOW):
            return False
        if TG_CATEGORIES_ALLOW and (cat not in TG_CATEGORIES_ALLOW):
            return False
        return True

    def send(self, text: str) -> None:
        if not self.enabled():
            return

        now = time.time()

        # global send rate-limit
        if now - self._last_sent_ts < TG_MIN_INTERVAL_S:
            return

        # TTL dedupe (content hash)
        self._gc(now)
        h = hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()
        last = self._dedupe.get(h)
        if last is not None and (now - last) <= max(1.0, TG_DEDUPE_TTL_S):
            return

        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = urllib.parse.urlencode(
                {"chat_id": TELEGRAM_CHAT_ID, "text": text}
            ).encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST")
            with urllib.request.urlopen(req, timeout=5) as resp:
                _ = resp.read()

            self._last_sent_ts = now
            self._dedupe[h] = now
        except Exception:
            # must be silent: notifications must never crash UI
            return


# ----------------------------- Panel -----------------------------

class NotificationsPanel:
    """Read-only notifications panel.

    Public API:
      - .frame
      - .update_from_snapshot(snapshot: dict)
    """

    def __init__(self, parent: tk.Misc) -> None:
        self._frame = ttk.Frame(parent, style="Dark.TFrame")

        top = ttk.Frame(self._frame, style="Dark.TFrame")
        top.pack(fill="x", padx=8, pady=(8, 6))

        ttk.Label(top, text="Notifications (read-only)", style="Muted.TLabel").pack(side=tk.LEFT)

        self._lbl_tg = ttk.Label(top, text="", style="Muted.TLabel")
        self._lbl_tg.pack(side=tk.RIGHT)

        # Controls
        ctrls = ttk.Frame(self._frame, style="Dark.TFrame")
        ctrls.pack(fill="x", padx=8, pady=(0, 6))

        ttk.Label(ctrls, text="Level:", style="Muted.TLabel").pack(side=tk.LEFT)
        self._level_var = tk.StringVar(value="ALL")
        self._level_cb = ttk.Combobox(ctrls, textvariable=self._level_var, values=("ALL",) + LEVELS, width=10, state="readonly")
        self._level_cb.pack(side=tk.LEFT, padx=(6, 12))

        ttk.Label(ctrls, text="Category:", style="Muted.TLabel").pack(side=tk.LEFT)
        self._cat_var = tk.StringVar(value="ALL")
        self._cat_cb = ttk.Combobox(ctrls, textvariable=self._cat_var, values=("ALL",) + CATEGORIES, width=10, state="readonly")
        self._cat_cb.pack(side=tk.LEFT, padx=(6, 12))

        ttk.Label(ctrls, text="Search:", style="Muted.TLabel").pack(side=tk.LEFT)
        self._q_var = tk.StringVar(value="")
        self._q_entry = ttk.Entry(ctrls, textvariable=self._q_var, width=30)
        self._q_entry.pack(side=tk.LEFT, padx=(6, 12))

        self._btn_clear = ttk.Button(ctrls, text="Clear", command=self.clear)
        self._btn_clear.pack(side=tk.RIGHT)

        # Table
        table_box = ttk.Frame(self._frame, style="Dark.TFrame")
        table_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        cols = ("time", "level", "category", "title", "message")
        self._tree = ttk.Treeview(table_box, columns=cols, show="headings", height=14)
        for c in cols:
            self._tree.heading(c, text=c)
        self._tree.column("time", width=80, stretch=False)
        self._tree.column("level", width=80, stretch=False)
        self._tree.column("category", width=90, stretch=False)
        self._tree.column("title", width=220, stretch=True)
        self._tree.column("message", width=600, stretch=True)

        vs = ttk.Scrollbar(table_box, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vs.set)
        self._tree.pack(side=tk.LEFT, fill="both", expand=True)
        vs.pack(side=tk.RIGHT, fill="y")

        # state
        self._items: Deque[Notification] = deque(maxlen=MAX_NOTIFS)
        self._tg = _TelegramSink()

        self._prev_safe: Optional[bool] = None
        self._prev_stale: Optional[bool] = None
        self._prev_open_sig: str = ""  # signature for open_position
        self._prev_mode: str = ""

        # PnL digest tracking
        self._last_pnl_sent_ts: float = 0.0
        self._last_pnl_total_pct: Optional[float] = None

        # UI updates on filter change
        self._level_cb.bind("<<ComboboxSelected>>", lambda _e: self._render())
        self._cat_cb.bind("<<ComboboxSelected>>", lambda _e: self._render())
        self._q_entry.bind("<KeyRelease>", lambda _e: self._render())

        self._refresh_tg_label()

    @property
    def frame(self) -> ttk.Frame:
        return self._frame

    def _refresh_tg_label(self) -> None:
        if self._tg.enabled():
            # show filters brief
            lvl = ",".join(sorted(TG_LEVELS_ALLOW)) if TG_LEVELS_ALLOW else "ALL"
            cat = ",".join(sorted(TG_CATEGORIES_ALLOW)) if TG_CATEGORIES_ALLOW else "ALL"
            self._lbl_tg.configure(text=f"Telegram: ON  (levels={lvl}; cats={cat})")
        else:
            if TELEGRAM_ENABLED and (not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID):
                self._lbl_tg.configure(text="Telegram: missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")
            else:
                self._lbl_tg.configure(text="Telegram: OFF (set MONTRIX_TELEGRAM_NOTIFY=1)")

    def clear(self) -> None:
        self._items.clear()
        for iid in self._tree.get_children():
            self._tree.delete(iid)

    # ----------------------------- Snapshot -> notifications -----------------------------

    def update_from_snapshot(self, snapshot: dict) -> None:
        if not isinstance(snapshot, dict):
            return

        now = time.time()

        safe = bool(snapshot.get("safe_mode") is True)
        # stale: prefer ui_stall (tick lag) + optional explicit stale flag
        stale = bool(snapshot.get("ui_stall") is True or snapshot.get("stale") is True)

        mode = str(snapshot.get("mode") or "").strip() or "—"

        # 1) SAFE transitions
        if self._prev_safe is None:
            self._prev_safe = safe
        elif safe != self._prev_safe:
            if safe:
                self._push(now, "WARNING", "SAFE", "SAFE MODE", "SAFE MODE engaged (system entered SAFE).")
            else:
                self._push(now, "INFO", "SAFE", "SAFE MODE", "SAFE MODE cleared (system recovered).")
            self._prev_safe = safe

        # 2) STALE transitions
        if self._prev_stale is None:
            self._prev_stale = stale
        elif stale != self._prev_stale:
            if stale:
                self._push(now, "WARNING", "STALE", "DATA STALE", "Market/UI feed appears stale (updates stalled).")
            else:
                self._push(now, "INFO", "STALE", "DATA STALE", "Feed recovered (updates resumed).")
            self._prev_stale = stale

        # 3) Mode transitions
        if not self._prev_mode:
            self._prev_mode = mode
        elif mode != self._prev_mode:
            self._push(now, "INFO", "SYSTEM", "MODE", f"Mode changed: {self._prev_mode} → {mode}")
            self._prev_mode = mode

        # 4) Trade lifecycle (best-effort via open_position)
        pos = snapshot.get("open_position")
        sig = self._pos_signature(pos)
        if sig != self._prev_open_sig:
            # open
            if sig and not self._prev_open_sig:
                sym = (pos or {}).get("symbol") if isinstance(pos, dict) else ""
                side = (pos or {}).get("side") if isinstance(pos, dict) else ""
                entry = (pos or {}).get("entry") if isinstance(pos, dict) else ""
                self._push(now, "INFO", "TRADE", "Position opened", f"{sym} {side} entry={entry}".strip())
            # close
            if (not sig) and self._prev_open_sig:
                self._push(now, "INFO", "TRADE", "Position closed", "Open position disappeared (closed/aborted).")
            self._prev_open_sig = sig

        # 5) Errors (best-effort: snapshot.last_error / snapshot.error)
        err = snapshot.get("last_error") or snapshot.get("error")
        if err:
            self._push(now, "ERROR", "ERROR", "Runtime error", str(err)[:500])

        # 6) PnL digest (optional)
        self._maybe_pnl_digest(now, snapshot)

        # Render once per update (cheap)
        self._render()

    def _maybe_pnl_digest(self, now: float, snapshot: dict) -> None:
        if not self._tg.enabled():
            return
        if not TG_PNL_DIGEST_ENABLED:
            return

        # Require at least one of these fields to exist
        pnl_total = snapshot.get("pnl_total_pct")
        equity = snapshot.get("equity")
        if pnl_total is None and equity is None:
            return

        try:
            pnl_total_f = float(pnl_total) if pnl_total is not None else None
        except Exception:
            pnl_total_f = None

        # Interval gate
        if now - self._last_pnl_sent_ts < max(10.0, TG_PNL_INTERVAL_S):
            return

        # Delta gate (only when pnl_total exists)
        if pnl_total_f is not None and self._last_pnl_total_pct is not None:
            if abs(pnl_total_f - self._last_pnl_total_pct) < max(0.0, TG_PNL_MIN_DELTA_PCT):
                return

        # Compose digest
        parts = []
        if equity is not None:
            try:
                parts.append(f"Equity: {float(equity):.2f}")
            except Exception:
                parts.append(f"Equity: {equity}")
        if pnl_total_f is not None:
            parts.append(f"Total PnL%: {pnl_total_f:.2f}")
        pnl_day = snapshot.get("pnl_day_pct")
        if pnl_day is not None:
            try:
                parts.append(f"Day PnL%: {float(pnl_day):.2f}")
            except Exception:
                parts.append(f"Day PnL%: {pnl_day}")

        msg = " | ".join(parts) if parts else "PnL update"

        # send as INFO/PNL, but filtered by env allow-lists
        self._push(now, "INFO", "PNL", "PnL digest", msg)

        self._last_pnl_sent_ts = now
        if pnl_total_f is not None:
            self._last_pnl_total_pct = pnl_total_f

    def _pos_signature(self, pos: Any) -> str:
        if not isinstance(pos, dict):
            return ""
        parts = [
            str(pos.get("symbol") or ""),
            str(pos.get("side") or ""),
            str(pos.get("entry") or ""),
            str(pos.get("id") or ""),
        ]
        s = "|".join(parts).strip("|")
        if not s:
            return ""
        return hashlib.sha1(s.encode("utf-8", errors="ignore")).hexdigest()

    def _push(self, ts: float, level: str, category: str, title: str, message: str) -> None:
        level = (level or "INFO").upper()
        if level not in LEVELS:
            level = "INFO"
        category = (category or "SYSTEM").upper()
        if category not in CATEGORIES:
            category = "SYSTEM"

        n = Notification(ts=ts, level=level, category=category, title=title, message=message, source="UI")
        self._items.append(n)

        # Optional telegram (filtered + dedupe TTL)
        if self._tg.allow(level, category):
            text = f"[{level}] {category}: {title}\n{message}"
            self._tg.send(text)

    # ----------------------------- Rendering -----------------------------

    def _render(self) -> None:
        lvl = str(self._level_var.get() or "ALL").upper()
        cat = str(self._cat_var.get() or "ALL").upper()
        q = str(self._q_var.get() or "").strip().lower()

        def _match(n: Notification) -> bool:
            if lvl != "ALL" and n.level != lvl:
                return False
            if cat != "ALL" and n.category != cat:
                return False
            if q:
                hay = f"{n.level} {n.category} {n.title} {n.message}".lower()
                return q in hay
            return True

        # redraw (small volumes; OK for v1)
        for iid in self._tree.get_children():
            self._tree.delete(iid)

        for n in list(self._items):
            if _match(n):
                self._tree.insert("", tk.END, values=n.to_row())
