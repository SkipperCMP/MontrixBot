# ui/strategy_registry.py
# v2.2.51 — Strategy Registry (read-only) powered by Strategy Contract v1
# UI-only: никакой власти, никаких side-effects, только отображение.

from __future__ import annotations

from typing import Any, Dict, List, Optional, Callable

import json
import time
from pathlib import Path
from collections import deque

import tkinter as tk
from tkinter import ttk

from ui.strategy_contract import StrategyContractV1, get_strategy_contracts_v1, get_ui_activity_throttle_sec

# -----------------------------------------------------------------------------
# Strategy activity badge (UI-only, read-only)
# -----------------------------------------------------------------------------
# Shows "recent activity" per strategy based on SIM_DECISION_JOURNAL events.
# Uses the same source preference as the Journal viewer:
#   - runtime/events.jsonl (if it contains SIM_DECISION_JOURNAL)
#   - otherwise runtime/logs/events.jsonl (if present)
#
# NOTE: This is UI-only and must not create/modify any runtime files.

_ACTIVITY_CACHE_TTL_SEC = 2.0
_ACTIVITY_TAIL_LINES = 6000

_activity_cache = {
    "ts_monotonic": 0.0,
    "path": None,        # str | None
    "last_ts": {},       # dict[str, float]
}


# Tail cache to avoid repeated full file reads (UI-only, read-only)
_JSONL_TAIL_CACHE: dict[str, dict] = {}


def _tail_lines(path: Path, max_lines: int) -> List[str]:
    """Return last `max_lines` lines using a small incremental cache.

    UI-only, best-effort:
    - reads only appended bytes when possible
    - resets cache on truncation/rotation
    """
    try:
        if not path.exists() or not path.is_file():
            return []

        st = path.stat()
        key = str(path)
        ent = _JSONL_TAIL_CACHE.get(key) or {}

        size = int(getattr(st, "st_size", 0) or 0)
        mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)) or 0)

        if (
            (not ent)
            or int(ent.get("size", -1)) > size
            or int(ent.get("mtime_ns", 0)) > mtime_ns
        ):
            ent = {
                "size": 0,
                "mtime_ns": 0,
                "pos": 0,
                "buf": b"",
                "lines": deque(maxlen=max(200, max_lines)),
            }

        dq = ent.get("lines")
        if not isinstance(dq, deque) or dq.maxlen != max(200, max_lines):
            dq = deque(list(dq) if isinstance(dq, deque) else [], maxlen=max(200, max_lines))
            ent["lines"] = dq

        pos = int(ent.get("pos", 0) or 0)
        buf = ent.get("buf", b"")
        if not isinstance(buf, (bytes, bytearray)):
            buf = b""

        if pos < 0 or pos > size:
            pos = 0
            buf = b""

        if size > pos:
            with path.open("rb") as f:
                f.seek(pos)
                chunk = f.read(size - pos)
            if chunk:
                buf = bytes(buf) + chunk
                parts = buf.splitlines(keepends=False)
                if not buf.endswith(b"\n") and not buf.endswith(b"\r"):
                    buf = parts.pop() if parts else b""
                else:
                    buf = b""

                for b in parts:
                    try:
                        s = b.decode("utf-8", errors="replace")
                    except Exception:
                        s = ""
                    s = (s or "").strip()
                    if s:
                        dq.append(s)

            ent["pos"] = size

        ent["size"] = size
        ent["mtime_ns"] = mtime_ns
        ent["buf"] = buf
        _JSONL_TAIL_CACHE[key] = ent

        return list(dq)[-max_lines:]
    except Exception:
        try:
            txt = path.read_text(encoding="utf-8", errors="replace")
            return txt.splitlines()[-max_lines:]
        except Exception:
            return []


def _resolve_journal_events_path() -> Optional[Path]:
    primary = Path("runtime") / "events.jsonl"
    fallback = Path("runtime") / "logs" / "events.jsonl"

    if primary.exists():
        tail = "\n".join(_tail_lines(primary, 2000))
        if "SIM_DECISION_JOURNAL" in tail:
            return primary

    if fallback.exists():
        return fallback

    if primary.exists():
        return primary

    return None


def _extract_strategy_id(evt: Dict[str, Any]) -> Optional[str]:
    if isinstance(evt.get("sid"), str) and evt.get("sid"):
        return evt["sid"]

    payload = evt.get("payload")
    if isinstance(payload, dict):
        for k in ("sid", "strategy_id", "strategy"):
            v = payload.get(k)
            if isinstance(v, str) and v:
                return v

    v2 = evt.get("strategy")
    if isinstance(v2, str) and v2:
        return v2

    return None


def _refresh_activity_cache() -> None:
    now_m = time.monotonic()
    if (now_m - float(_activity_cache.get("ts_monotonic") or 0.0)) < _ACTIVITY_CACHE_TTL_SEC:
        return

    path = _resolve_journal_events_path()
    last_ts: Dict[str, float] = {}

    if path is not None and path.exists():
        for line in _tail_lines(path, _ACTIVITY_TAIL_LINES):
            if not line or "SIM_DECISION_JOURNAL" not in line:
                continue
            try:
                evt = json.loads(line)
            except Exception:
                continue
            if not isinstance(evt, dict):
                continue
            if evt.get("type") != "SIM_DECISION_JOURNAL":
                continue

            sid = _extract_strategy_id(evt)
            if not sid:
                continue

            ts = evt.get("ts")
            if isinstance(ts, (int, float)):
                if ts > last_ts.get(sid, 0.0):
                    last_ts[sid] = float(ts)

    _activity_cache["ts_monotonic"] = now_m
    _activity_cache["path"] = str(path) if path is not None else None
    _activity_cache["last_ts"] = last_ts


def _get_activity_last_ts_map() -> Dict[str, float]:
    """Return cached last-ts map for strategy activity (best-effort)."""
    _refresh_activity_cache()
    last_ts = _activity_cache.get("last_ts") or {}
    return last_ts if isinstance(last_ts, dict) else {}


def _format_activity_badge(age_sec: float) -> str:
    """Format activity age similarly to Journal cache age (seconds-first)."""
    try:
        age = float(age_sec)
    except Exception:
        return "—"

    if age < 0:
        return "—"
    if age < 60:
        # seconds-first semantics (align with Journal badge)
        return f"{int(age)}s"
    if age < 3600:
        return f"{int(age // 60)}m"
    if age < 24 * 3600:
        return f"{int(age // 3600)}h"
    return "—"


def get_strategy_activity_badge(sid: str) -> str:
    last_ts = _get_activity_last_ts_map()
    ts = last_ts.get(sid)
    if not isinstance(ts, (int, float)):
        return "—"
    age = time.time() - float(ts)
    return _format_activity_badge(age)


def refresh_tree_activity(tree: ttk.Treeview, by_id: Dict[str, StrategyContractV1]) -> None:
    # Throttle UI churn: registry activity badges may be refreshed from multiple places
    # (global refresh loop + local scheduler). We guard updates to avoid frequent tree.item().
    try:
        throttle_sec = float(get_ui_activity_throttle_sec() or 0.0)
    except Exception:
        throttle_sec = 0.0

    if throttle_sec > 0.0:
        try:
            now_m = time.monotonic()
            last_m = float(getattr(tree, "_mb_activity_refresh_m", 0.0) or 0.0)
            if (now_m - last_m) < throttle_sec:
                return
            setattr(tree, "_mb_activity_refresh_m", now_m)
        except Exception:
            # never fail hard in UI-only code
            pass

    try:
        last_ts = _get_activity_last_ts_map()
        now_t = time.time()
        for item_id, contract in by_id.items():
            ts = last_ts.get(contract.sid)
            if not isinstance(ts, (int, float)):
                badge = "—"
            else:
                badge = _format_activity_badge(now_t - float(ts))
            tree.item(item_id, values=(contract.status, badge))
    except Exception:
        return


def get_strategy_registry_v1() -> Optional[Dict[str, Any]]:
    """Return contracts for display."""
    return get_strategy_contracts_v1()


def build_strategy_registry_tab(
    app: Any,
    parent: Any,
    open_journal_cb: Optional[Callable[..., Any]] = None,
) -> None:
    """Mount read-only Strategy Registry UI into `parent` (Strategies tab frame)."""
    root = ttk.Frame(parent, style="Dark.TFrame")
    root.pack(fill="both", expand=True, padx=8, pady=8)

    title = ttk.Label(root, text="Strategy Registry (read-only)", style="Dark.TLabel")
    title.pack(anchor="w", pady=(0, 6))

    hint = ttk.Label(
        root,
        text="Стратегии — это объекты поведения без власти. Здесь только просмотр.",
        style="Muted.TLabel",
    )
    hint.pack(anchor="w", pady=(0, 10))

    actions = ttk.Frame(root, style="Dark.TFrame")
    actions.pack(fill="x", pady=(0, 10))

    btn_open_journal = ttk.Button(actions, text="Open SIM Journal", style="Dark.TButton")
    btn_open_journal.pack(side="left")

    body = ttk.Frame(root, style="Dark.TFrame")
    body.pack(fill="both", expand=True)

    left = ttk.Frame(body, style="Dark.TFrame")
    left.pack(side="left", fill="y")

    right = ttk.Frame(body, style="Dark.TFrame")
    right.pack(side="left", fill="both", expand=True, padx=(12, 0))

    ttk.Label(left, text="Strategies", style="Dark.TLabel").pack(anchor="w")

    tree = ttk.Treeview(left, columns=("status", "activity"), show="tree headings", height=14)
    tree.heading("#0", text="Name")
    tree.heading("status", text="Status")
    tree.heading("activity", text="Activity")
    tree.column("#0", width=220, stretch=False)
    tree.column("status", width=120, stretch=False)
    tree.column("activity", width=90, stretch=False)
    tree.pack(fill="y", expand=False, pady=(6, 0))

    def _on_open_journal_clicked() -> None:
        sid: Optional[str] = None
        try:
            sel = tree.selection()
            if sel:
                item = by_id.get(sel[0])
                if item is not None:
                    sid = getattr(item, "sid", None)
        except Exception:
            sid = None

        cb = open_journal_cb
        if cb is None:
            cb = getattr(app, "_ui_deeplink_open_sim_journal", None)

        if cb is None:
            return

        try:
            cb(sid)
        except TypeError:
            # backward-compatible: callback may accept no args
            cb()
        except Exception:
            return

    try:
        btn_open_journal.configure(command=_on_open_journal_clicked)

        # UI-only hook: let the global refresh loop update activity badges
        def _refresh_strategy_activity_badges() -> None:
            try:
                refresh_tree_activity(tree, by_id)
            except Exception:
                return

        setattr(app, "_refresh_strategy_activity_badges", _refresh_strategy_activity_badges)
    except Exception:
        pass

    ttk.Label(right, text="Details", style="Dark.TLabel").pack(anchor="w")

    details = tk.Text(
        right,
        height=18,
        wrap="word",
        bg="#0f1216",
        fg="#E6EAF2",
        insertbackground="#E6EAF2",
        relief="flat",
        highlightthickness=1,
        highlightbackground="#171B21",
        highlightcolor="#171B21",
    )
    details.pack(fill="both", expand=True, pady=(6, 0))

    def set_details(txt: str) -> None:
        details.configure(state="normal")
        details.delete("1.0", "end")
        details.insert("1.0", txt)
        details.configure(state="disabled")

    reg = get_strategy_registry_v1()
    by_id: Dict[str, StrategyContractV1] = {}

    for s in reg:
        name = (s.name or "").strip() or "Unnamed"
        status = (s.status or "").strip() or "unknown"
        iid = f"strat::{s.sid}"
        by_id[iid] = s
        tree.insert("", "end", iid=iid, text=name, values=(status, "—"))

    def render_strategy(s: StrategyContractV1) -> str:
        lines: List[str] = []
        lines.append(f"ID: {s.sid}")
        lines.append(f"Name: {s.name}")
        lines.append(f"Status: {s.status}")
        lines.append(f"Risk: {s.risk_profile}")
        lines.append("")
        lines.append("Purpose:")
        lines.append(f"  {s.purpose}")
        lines.append("")
        lines.append("Inputs:")
        if s.inputs:
            for x in s.inputs:
                lines.append(f"  - {x}")
        else:
            lines.append("  (none)")
        lines.append("")
        lines.append("Outputs:")
        if s.outputs:
            for x in s.outputs:
                lines.append(f"  - {x}")
        else:
            lines.append("  (none)")
        lines.append("")
        lines.append("Params:")
        if s.params:
            for k in sorted(s.params.keys()):
                lines.append(f"  - {k}: {s.params[k]}")
        else:
            lines.append("  (none)")
        lines.append("")
        lines.append("Params schema:")
        if s.params_schema:
            for k in sorted(s.params_schema.keys()):
                meta = s.params_schema[k] or {}
                t = meta.get("type", "?")
                d = meta.get("default", "")
                desc = meta.get("desc", "")
                lines.append(f"  - {k}: type={t}, default={d}")
                if desc:
                    lines.append(f"      {desc}")
        else:
            lines.append("  (none)")
        return "\n".join(lines)

    def on_select(_evt=None):
        sel = tree.selection()
        if not sel:
            return
        iid = sel[0]
        s = by_id.get(iid)
        if not s:
            return
        set_details(render_strategy(s))

    tree.bind("<<TreeviewSelect>>", on_select)

    children = tree.get_children("")
    if children:
        tree.selection_set(children[0])
        tree.focus(children[0])
        on_select()

    # keep refs on app (debug stability, no behavior)
    app._strategy_registry_root = root
    app._strategy_registry_tree = tree
    app._strategy_registry_details = details

    def _focus_sid(sid: str) -> bool:
        """Focus/select a strategy by sid in the registry tree (UI-only)."""
        sid = str(sid or "").strip()
        if not sid:
            return False
        try:
            for iid in tree.get_children(""):
                s = by_id.get(iid)
                if not s:
                    continue
                if str(getattr(s, "sid", "") or "").strip() == sid:
                    tree.selection_set(iid)
                    tree.focus(iid)
                    tree.see(iid)
                    on_select()
                    return True
        except Exception:
            return False
        return False

    # public hook for deep-links (Journal → Registry)
    app._strategy_registry_focus_sid = _focus_sid

    def _refresh_activity_badges() -> None:
        """Update Activity column using unified "age" semantics (UI-only)."""
        try:
            refresh_tree_activity(tree, by_id)
        except Exception:
            return

    def _schedule_activity_refresh() -> None:
        _refresh_activity_badges()
        try:
            root.after(5000, _schedule_activity_refresh)
        except Exception:
            pass

    _schedule_activity_refresh()
