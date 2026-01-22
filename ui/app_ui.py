# MontrixBot
# UI-лаунчер с:
#  - Buy/Close/Panic через UIAPI (core-owned)
#  - SAFE-индикатором
#  - просмотром журнала / runtime-папки
#  - статическим и LIVE-чартом (Price + RSI + MACD)
#  - простыми сигналами по RSI+MACD (core.signals.simple_rsi_macd_signal)

from __future__ import annotations

import importlib
import os
import subprocess
import sys
import time
from collections import deque
from pathlib import Path
from typing import List, Tuple, Optional

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from tools.exporting import export_sim_journal_entries


# Dark-тема вынесена в отдельный модуль (Step 1.2.8)
try:
    from .theme_dark import apply_neutral_dark
except Exception:
    try:
        from ui.theme_dark import apply_neutral_dark
    except Exception:
        apply_neutral_dark = None  # type: ignore[assignment]


from ui.layout.topbar import create_topbar
from ui.layout.positions_panel import create_positions_panel
from ui.layout.deals_panel import create_deals_panel
from ui.layout.styles import apply_styles

from ui.controllers.mode_controller import ModeController
from ui.controllers.positions_controller import PositionsController
from ui.controllers.chart_controller import ChartController
from ui.controllers.autosim_controller import AutosimController

from ui.services.snapshot_service import SnapshotService
from ui.services.ui_updater import UIRefreshService
from ui.services.tick_updater import TickUpdater
from ui.events.subscribers import install_default_ui_subscribers

# ---------------------------------------------------------------------------
#  Универсальные импорты ChartPanel / indicators / signals
# ---------------------------------------------------------------------------

def _ensure_project_root_on_syspath() -> None:
    """Best-effort: ensure project root is on sys.path (script-style runs only).

    IMPORTANT:
    - When running as a package (imported as ui.* / launched via ui/main_app.py),
      we must NOT mutate sys.path.
    - Only allow sys.path tweak for rare direct script-style runs (debug only).
    """
    try:
        # Package-run (normal path): do not touch sys.path.
        # In package mode __package__ is usually "ui".
        if __package__:
            return
    except Exception:
        # If we cannot reliably detect package mode, keep best-effort behavior.
        pass

    try:
        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
    except Exception:
        pass


def _import_module(module_name: str):
    """Import a module by name. Returns (module_or_None, error_or_None)."""
    try:
        mod = importlib.import_module(module_name)
        return mod, None
    except Exception as e:  # noqa: BLE001
        return None, e


def _import_attr(module_name: str, attr_name: str):
    """Import module then getattr(attr). Returns (obj_or_None, error_or_None)."""
    mod, err = _import_module(module_name)
    if mod is None:
        return None, err
    try:
        return getattr(mod, attr_name), None
    except Exception as e:  # noqa: BLE001
        return None, e


def _try_import_chartpanel():
    last_error = None
    # 1) запуск как пакет: python -m ui.main_app
    try:
        from .widgets.chart_panel import ChartPanel as _CP  # type: ignore
        return _CP, None
    except Exception as e:  # noqa: BLE001
        last_error = e

    # 2) запуск как скрипт: python ui/main_app.py
    _ensure_project_root_on_syspath()
    obj, err = _import_attr("ui.widgets.chart_panel", "ChartPanel")
    if obj is not None:
        return obj, None
    return None, err if err is not None else last_error


def _try_import_uiapi():
    last_error = None

    # 1) нормальный путь (package-run): ничего не трогаем
    obj, err = _import_attr("core.ui_api", "UIAPI")
    if obj is not None:
        return obj, None
    last_error = err

    # 2) fallback для script-run
    _ensure_project_root_on_syspath()
    obj, err = _import_attr("core.ui_api", "UIAPI")
    if obj is not None:
        return obj, None

    return None, err if err is not None else last_error


def _try_import_statusbar():
    last_error = None
    # 1) запуск как пакет: python -m ui.main_app
    try:
        from .widgets.status_bar import StatusBar as _SB  # type: ignore
        return _SB, None
    except Exception as e:  # noqa: BLE001
        last_error = e

    # 2) запуск как скрипт: python ui/main_app.py
    _ensure_project_root_on_syspath()
    obj, err = _import_attr("ui.widgets.status_bar", "StatusBar")
    if obj is not None:
        return obj, None
    return None, err if err is not None else last_error


def _try_import_dealsjournal():
    last_error = None
    # 1) запуск как пакет: python -m ui.main_app
    try:
        from .widgets.deals_journal import DealsJournal as _DJ  # type: ignore
        return _DJ, None
    except Exception as e:  # noqa: BLE001
        last_error = e

    # 2) запуск как скрипт: python ui/main_app.py
    _ensure_project_root_on_syspath()
    obj, err = _import_attr("ui.widgets.deals_journal", "DealsJournal")
    if obj is not None:
        return obj, None
    return None, err if err is not None else last_error


def _try_import_indicators():
    last_error = None

    # 1) нормальный путь (package-run)
    mod, err = _import_module("core.indicators")
    if mod is not None:
        return mod, None
    last_error = err

    # 2) fallback для script-run
    _ensure_project_root_on_syspath()
    mod, err = _import_module("core.indicators")
    if mod is not None:
        return mod, None

    return None, err if err is not None else last_error


def _try_import_signals():
    last_error = None

    # 1) нормальный путь (package-run)
    mod, err = _import_module("core.signals")
    if mod is not None:
        return mod, None
    last_error = err

    # 2) fallback для script-run
    _ensure_project_root_on_syspath()
    mod, err = _import_module("core.signals")
    if mod is not None:
        return mod, None

    return None, err if err is not None else last_error


def _try_import_advisor():
    last_error = None

    # 1) нормальный путь (package-run)
    mod, err = _import_module("core.advisor")
    if mod is not None:
        return mod, None
    last_error = err

    # 2) fallback для script-run
    _ensure_project_root_on_syspath()
    mod, err = _import_module("core.advisor")
    if mod is not None:
        return mod, None

    return None, err if err is not None else last_error


def _try_import_autosim():
    last_error = None

    # 1) нормальный путь (package-run)
    mod, err = _import_module("core.sim.auto_from_signals")
    if mod is None:
        last_error = err
    else:
        try:
            AutoSimFromSignals = getattr(mod, "AutoSimFromSignals")
            AutoSimConfig = getattr(mod, "AutoSimConfig")
            return (AutoSimFromSignals, AutoSimConfig), None
        except Exception as e:  # noqa: BLE001
            last_error = e

    # 2) fallback для script-run
    _ensure_project_root_on_syspath()
    mod, err = _import_module("core.sim.auto_from_signals")
    if mod is None:
        return None, err if err is not None else last_error

    try:
        AutoSimFromSignals = getattr(mod, "AutoSimFromSignals")
        AutoSimConfig = getattr(mod, "AutoSimConfig")
        return (AutoSimFromSignals, AutoSimConfig), None
    except Exception as e:  # noqa: BLE001
        return None, e


def _try_import_toast():
    last_error = None
    # 1) запуск как пакет: python -m ui.main_app
    try:
        from .widgets.toast_manager import ToastManager as _TM  # type: ignore
        return _TM, None
    except Exception as e:  # noqa: BLE001
        last_error = e

    # 2) запуск как скрипт: python ui/main_app.py
    _ensure_project_root_on_syspath()
    obj, err = _import_attr("ui.widgets.toast_manager", "ToastManager")
    if obj is not None:
        return obj, None
    return None, err if err is not None else last_error

# --- runtime bootstrap helper (best-effort) ---
try:
    from tools.runtime_bootstrap import ensure_ticks_bootstrap
except Exception:  # fallback: no-op
    def ensure_ticks_bootstrap(
        symbol: str,
        max_points: int = 300,
        interval: str = "1m",
        min_points: int = 50,
    ) -> int:
        return 0

ChartPanel, _CHART_ERR = _try_import_chartpanel()
StatusBar, _STATUS_ERR = _try_import_statusbar()
DealsJournal, _JOURNAL_ERR = _try_import_dealsjournal()
INDICATORS, _IND_ERR = _try_import_indicators()
SIGNALS, _SIG_ERR = _try_import_signals()
ADVISOR, _ADV_ERR = _try_import_advisor()
UIAPI, _UI_ERR = _try_import_uiapi()
AUTOSIM_FACTORY, _AUTOSIM_ERR = _try_import_autosim()
ToastManager, _TOAST_ERR = _try_import_toast()

# ---------------------------------------------------------------------------
#  Константы путей
# ---------------------------------------------------------------------------

APP_TITLE = "MontrixBot"
ROOT_DIR = Path(__file__).resolve().parent.parent
SAFE_FILE = ROOT_DIR / "SAFE_MODE"
SCRIPTS_DIR = ROOT_DIR / "scripts"
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT"]

# v2.2.34 — Stale marker threshold for top status line (read-only)
STALE_STATUS_AGE_SEC = 30

# v2.2.35 — Event spine peek (read-only)
EVENT_SPINE_PEEK_N = 5
EVENTS_JSONL_PATH = ROOT_DIR / "runtime" / "events.jsonl"

# v2.2.48 — RU Reason Map (UI-only, display-only)
# Единственная задача: человекочитаемое отображение причин.
# Контракты и ключи (MODE_MANUAL_ONLY, MANUAL_STOP, etc.) НЕ меняем.

def format_why_not(why):
    """
    UI read-only formatting.

    Правило: UI НЕ интерпретирует причины и НЕ теряет хвост.
    Показываем весь список как есть, но с человекочитаемым отображением (RU),
    где это возможно. Fallback — исходный код.
    """
    if not isinstance(why, list) or not why:
        return ""

    # локальный импорт: UI-only
    try:
        from ui.reasons_map import human_reason  # type: ignore
    except Exception:
        def human_reason(x):  # type: ignore
            return x

    parts = []
    for x in why:
        s = str(x).strip()
        if s:
            parts.append(str(human_reason(s)))

    return " | ".join(parts)

def format_gate_tag(gate):
    """
    UI-only helper (display-only).
    Returns a compact single-line tag for topbar:
      - "GATE=ALLOW"
      - "GATE=VETO:MANUAL_STOP+"
      - "GATE=VETO"
    """
    if not isinstance(gate, dict) or not gate:
        return ""
    decision = str(gate.get("decision") or "").upper() or "N/A"
    if decision == "ALLOW":
        return "GATE=ALLOW"
    reasons = gate.get("reasons") or []
    if not isinstance(reasons, list):
        reasons = []
    if decision == "VETO":
        if reasons:
            head = str(reasons[0])[:24]
            suffix = "+" if len(reasons) > 1 else ""
            return f"GATE=VETO:{head}{suffix}"
        return "GATE=VETO"
    return f"GATE={decision}"


def format_explain_panel(payload: dict) -> str:
    """
    UI-only explainability (read-only).
    Combines:
      - why_not (list[str])
      - gate_last (decision/reasons/evidence)
      - SIM decision trace & silence explainability (events-only, persisted journal)
    """
    if not isinstance(payload, dict):
        return ""

    # local imports (UI-only; never affect core)
    try:
        import json  # type: ignore
    except Exception:
        json = None  # type: ignore
    try:
        import ast  # type: ignore
    except Exception:
        ast = None  # type: ignore
    try:
        from pathlib import Path  # type: ignore
    except Exception:
        Path = None  # type: ignore
    try:
        import time  # type: ignore
    except Exception:
        time = None  # type: ignore

    # helper: safe reason mapping (UI-only)
    try:
        from ui.reasons_map import human_reason  # type: ignore
    except Exception:
        def human_reason(x):  # type: ignore
            return x

    # --------------------
    #  WHY NOT
    # --------------------
    lines = []
    why = payload.get("why_not", None)
    if isinstance(why, list) and why:
        lines.append("WHY NOT:")
        for r in why[:10]:
            s = str(r).strip()
            if s:
                lines.append(f"  - {human_reason(s)}")
        if len(why) > 10:
            lines.append(f"  … +{len(why) - 10} more")

    # --------------------
    #  GATE LAST (cache)
    # --------------------
    gl = payload.get("gate_last", None)
    if isinstance(gl, dict) and gl:
        decision = str(gl.get("decision") or "").strip()
        reasons = gl.get("reasons") or []
        evidence = gl.get("evidence") or {}

        if lines:
            lines.append("")
        lines.append("GATE LAST:")
        if decision:
            lines.append(f"  decision: {decision}")

        if isinstance(reasons, list) and reasons:
            lines.append("  reasons:")
            for r in reasons[:8]:
                s = str(r).strip()
                if s:
                    lines.append(f"    - {human_reason(s)}")
            if len(reasons) > 8:
                lines.append(f"    … +{len(reasons) - 8} more")

        if isinstance(evidence, list):
            # legacy: evidence as list
            if evidence:
                lines.append(f"  evidence: {len(evidence)} items")
        elif isinstance(evidence, dict):
            # pretty-print compact evidence keys (avoid noise)
            try:
                keys = list(evidence.keys())
            except Exception:
                keys = []
            if keys:
                keys = sorted([str(k) for k in keys])[:18]
                lines.append(f"  evidence_keys: {', '.join(keys)}")

    # --------------------
    #  SIM — decision trace
    # --------------------
    def _resolve_events_path():
        if Path is None:
            return None
        # canonical first, then legacy mirror
        candidates = [
            Path("runtime") / "events.jsonl",
            Path("runtime") / "logs" / "events.jsonl",
        ]
        for p in candidates:
            try:
                if p.exists() and p.is_file():
                    return p
            except Exception:
                pass
        # if none exists, still return canonical location (debug-friendly)
        try:
            return candidates[0]
        except Exception:
            return None

    def _parse_event_line(line: str):
        s = (line or "").strip()
        if not s:
            return None
        # accept JSON or python-dict single quotes
        try:
            if json is not None:
                return json.loads(s)
        except Exception:
            pass
        try:
            if ast is not None:
                obj = ast.literal_eval(s)
                if isinstance(obj, dict):
                    return obj
        except Exception:
            pass
        return None

    def _read_tail_events(path_obj, max_lines=260):
        if path_obj is None:
            return []
        try:
            if hasattr(path_obj, "read_text"):
                # Path-like
                txt_lines = path_obj.read_text(encoding="utf-8", errors="replace").splitlines()
            else:
                # string path
                with open(str(path_obj), "r", encoding="utf-8", errors="replace") as f:
                    txt_lines = f.read().splitlines()
        except Exception:
            return []
        if not txt_lines:
            return []
        tail = txt_lines[-max_lines:]
        out = []
        for ln in tail:
            obj = _parse_event_line(ln)
            if isinstance(obj, dict):
                out.append(obj)
        return out

    def _fmt_conf(v):
        try:
            return f"{float(v):.3f}"
        except Exception:
            return str(v)

    def _extract_side(evt: dict) -> str:
        try:
            pl = evt.get("payload") or {}
            # common places
            for k in ("side", "input_side", "recommended_action"):
                v = pl.get(k)
                if v:
                    s = str(v).upper().strip()
                    if s in ("BUY", "SELL"):
                        return s
            # nested signals (SIM_DECISION_JOURNAL)
            sig = pl.get("signals") or {}
            if isinstance(sig, dict):
                v = sig.get("input_side")
                if v:
                    s = str(v).upper().strip()
                    if s in ("BUY", "SELL"):
                        return s
            # message heuristic
            msg = evt.get("msg") or evt.get("message") or ""
            msg = str(msg).upper()
            if "BUY" in msg and "SELL" not in msg:
                return "BUY"
            if "SELL" in msg and "BUY" not in msg:
                return "SELL"
        except Exception:
            pass
        return ""

    # strategy v1 constants (do NOT import core here; UI-only deterministic defaults)
    COOLDOWN_S = 30.0
    CONF_MIN = 0.60

    ev_path = _resolve_events_path()
    evs = _read_tail_events(ev_path, max_lines=260)

    # last committed decision (rare)
    last_dec = None
    for e in reversed(evs):
        if str(e.get("type") or "") == "SIM_DECISION_JOURNAL":
            last_dec = e
            break

    # recent signal sides (best-effort; noisy by design)
    recent_sides = []
    for e in reversed(evs):
        if str(e.get("type") or "") == "SIGNAL":
            sd = _extract_side(e)
            if sd:
                recent_sides.append(sd)
            if len(recent_sides) >= 12:
                break
    unique_sides = sorted(set(recent_sides))
    conflicting = ("BUY" in unique_sides) and ("SELL" in unique_sides)

    sim_block = []
    sim_block.append("SIM:")

    now_ts = None
    try:
        if time is not None:
            now_ts = float(time.time())
    except Exception:
        now_ts = None

    # DECISION TRACE (why no decision now)
    sim_block.append("DECISION TRACE:")
    trace_status = "MARKET_STABLE_NO_ACTION"
    cooldown_remaining = None

    if not isinstance(last_dec, dict):
        trace_status = "NO_DECISION_YET"
    else:
        # cooldown based on last journal commit timestamp
        ts = last_dec.get("ts")
        age_s = None
        try:
            if now_ts is not None and isinstance(ts, (int, float)):
                age_s = max(0.0, now_ts - float(ts))
        except Exception:
            age_s = None

        if isinstance(age_s, (int, float)) and age_s < COOLDOWN_S:
            trace_status = "COOLDOWN_ACTIVE"
            cooldown_remaining = max(0.0, COOLDOWN_S - float(age_s))
        elif conflicting:
            trace_status = "CONFLICTING_SIGNALS"
        elif unique_sides:
            trace_status = "NO_STRONG_CONFIRMATION"
        else:
            trace_status = "NO_SIGNAL_EVENTS"

    sim_block.append(f"  status: {trace_status}")

    # last committed decision details (if any)
    if isinstance(last_dec, dict):
        pl = last_dec.get("payload") or {}
        ts = last_dec.get("ts")
        rec = str(pl.get("recommended_action") or "").upper().strip()
        conf = pl.get("confidence", None)

        # show last decision timestamp + age (best-effort)
        if ts is not None:
            sim_block.append(f"  last_decision_ts: {ts}")
        try:
            if now_ts is not None and isinstance(ts, (int, float)):
                age_s = max(0.0, now_ts - float(ts))
                sim_block.append(f"  age_s: {age_s:.1f}")
        except Exception:
            pass

        if rec:
            sim_block.append(f"  last_action: {rec}")
        if conf is not None:
            sim_block.append(f"  last_confidence: {_fmt_conf(conf)}")

        if cooldown_remaining is not None:
            sim_block.append(f"  cooldown_remaining_s: {cooldown_remaining:.1f}")

        # keep the existing “rare decision” hints
        sig = pl.get("signals") or {}
        if isinstance(sig, dict):
            inp = sig.get("input_side")
            if inp:
                sim_block.append(f"  input_side: {str(inp).upper().strip()}")

        hyp = str(pl.get("hypothesis") or "").strip()
        if hyp:
            if len(hyp) > 120:
                hyp = hyp[:117] + "..."
            sim_block.append(f"  hyp: {hyp}")

    else:
        sim_block.append("  journal: empty (no committed decisions)")

    # Silence reason (human, UI-only)
    sim_block.append("SILENCE REASON:")

    if trace_status == "COOLDOWN_ACTIVE":
        sim_block.append(f"  - cooldown active (publish >= {CONF_MIN:.2f} & side BUY/SELL, cooldown {int(COOLDOWN_S)}s)")
    elif trace_status == "CONFLICTING_SIGNALS":
        sim_block.append("  - last signals are conflicting (BUY & SELL)")
    elif trace_status == "NO_STRONG_CONFIRMATION":
        sim_block.append(f"  - no strong confirmation (last side={unique_sides[0]})")
    elif trace_status == "NO_SIGNAL_EVENTS":
        sim_block.append("  - no SIGNAL events in persisted log (signals are live-only)")
    elif trace_status == "NO_DECISION_YET":
        sim_block.append("  - no committed decisions yet (SIM is observing)")
    else:
        sim_block.append("  - stable conditions (no publish-worthy change)")

    # attach
    if sim_block:
        if lines:
            lines.append("")
        lines.extend(sim_block)
        try:
            if ev_path:
                lines.append(f"source: {getattr(ev_path, 'as_posix', lambda: str(ev_path))()}")
        except Exception:
            pass

    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
#  events.jsonl tail cache (UI-only, read-only)
# ---------------------------------------------------------------------------
# Goal: avoid re-reading the whole events.jsonl on every UI refresh.
# This cache reads only appended bytes (best-effort) and keeps a bounded tail.

_JSONL_TAIL_CACHE: dict[str, dict] = {}


def _read_jsonl_tail_lines(path: str, max_lines: int = 2000) -> List[str]:
    """Read up to max_lines from the *end* of a JSONL file using a small incremental cache.

    Cache key: (path, max_lines)
    Cache fields:
      - lines: deque[str] (bounded)
      - pos: last read byte position
      - size: last known size
      - mtime_ns: last known mtime ns
      - last_read_m: monotonic timestamp of last *cache update* (not every UI refresh)
      - last_read_ts: wall-clock epoch seconds of last *cache update* (for badge HH:MM:SS)
    """
    key = (path, int(max_lines))
    now_m = time.monotonic()
    now_ts = time.time()

    try:
        st = os.stat(path)
    except FileNotFoundError:
        # If file disappears, keep cache entry (if any) but do not update last_read_*.
        # Caller will handle "missing" diagnostics separately.
        ent = _JSONL_TAIL_CACHE.get(key)
        return list(ent["lines"]) if ent else []

    ent = _JSONL_TAIL_CACHE.get(key)
    if ent is None:
        ent = {
            "lines": deque(maxlen=int(max_lines)),
            "pos": 0,
            "size": 0,
            "mtime_ns": 0,
            "last_read_m": 0.0,
            "last_read_ts": 0.0,
        }
        _JSONL_TAIL_CACHE[key] = ent

    # Fast path: unchanged file -> do NOT bump last_read_*
    if ent.get("size") == st.st_size and ent.get("mtime_ns") == getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)):
        return list(ent["lines"])

    updated = False
    mtime_ns = getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))

    # Handle truncation/rotation: file got smaller than our position
    if st.st_size < int(ent.get("pos", 0)):
        ent["lines"] = deque(maxlen=int(max_lines))
        ent["pos"] = 0
        ent["size"] = 0
        ent["mtime_ns"] = 0
        updated = True  # cache changed (reset)

    try:
        with open(path, "rb") as f:
            f.seek(int(ent.get("pos", 0)))
            chunk = f.read()
            if chunk:
                # Decode leniently; JSONL is expected UTF-8 but we tolerate bad bytes.
                text_chunk = chunk.decode("utf-8", errors="replace")
                for line in text_chunk.splitlines():
                    if line:
                        ent["lines"].append(line)
                updated = True
            ent["pos"] = f.tell()
    except Exception:
        # Do not destroy cache on transient read errors; do not bump last_read_*.
        return list(ent["lines"])

    ent["size"] = st.st_size
    ent["mtime_ns"] = mtime_ns

    # IMPORTANT: only bump last_read_* if cache was actually updated
    if updated:
        ent["last_read_m"] = now_m
        ent["last_read_ts"] = now_ts

    return list(ent["lines"])

    ent = _JSONL_TAIL_CACHE.get(key)
    if ent is None:
        ent = {
            "lines": deque(maxlen=int(max_lines)),
            "pos": 0,
            "size": 0,
            "mtime_ns": 0,
            "last_read_m": 0.0,
        }
        _JSONL_TAIL_CACHE[key] = ent

    # Fast path: unchanged file -> do NOT bump last_read_m
    if ent.get("size") == st.st_size and ent.get("mtime_ns") == getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)):
        return list(ent["lines"])

    updated = False
    mtime_ns = getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))

    # Handle truncation/rotation: file got smaller than our position
    if st.st_size < int(ent.get("pos", 0)):
        ent["lines"] = deque(maxlen=int(max_lines))
        ent["pos"] = 0
        ent["size"] = 0
        ent["mtime_ns"] = 0
        updated = True  # cache changed (reset)

    try:
        with open(path, "rb") as f:
            f.seek(int(ent.get("pos", 0)))
            chunk = f.read()
            if chunk:
                # Decode leniently; JSONL is expected UTF-8 but we tolerate bad bytes.
                text_chunk = chunk.decode("utf-8", errors="replace")
                for line in text_chunk.splitlines():
                    if line:
                        ent["lines"].append(line)
                updated = True
            ent["pos"] = f.tell()
    except Exception:
        # Do not destroy cache on transient read errors; do not bump last_read_m.
        return list(ent["lines"])

    ent["size"] = st.st_size
    ent["mtime_ns"] = mtime_ns

    # IMPORTANT: only bump last_read_m if cache was actually updated
    if updated:
        ent["last_read_m"] = now_m

    return list(ent["lines"])


def _get_jsonl_tail_cache_stats(path: str, max_lines: int = 2000) -> Dict[str, Any]:
    """Return small diagnostics for the JSONL tail cache (used by Journal badge).

    Adds explicit age_label states for UX (short labels to fit in top badge):
      - "— (miss)"    file missing
      - "— (no-read)" cache not created yet (no reads)
      - "— (empty)"   file exists but cache has no updates/lines
      - "{N}s"        cache age in seconds

    Adds last_read_label:
      - "—" or "HH:MM:SS"
    """
    key = (path, int(max_lines))

    # NOTE: keep cache key based on the original "path" object (can be Path or str).
    # For filesystem checks, normalize via Path().
    p = Path(path)

    if not (p.exists() and p.is_file()):
        return {
            "cached_lines": 0,
            "pos": 0,
            "size": 0,
            "age_s": None,
            "age_state": "FILE_MISSING",
            "age_label": "— (miss)",
            "last_read_ts": None,
            "last_read_label": "—",
        }

    ent = _JSONL_TAIL_CACHE.get(key)
    if ent is None:
        return {
            "cached_lines": 0,
            "pos": 0,
            "size": 0,
            "age_s": None,
            "age_state": "NO_READ_YET",
            "age_label": "— (no-read)",
            "last_read_ts": None,
            "last_read_label": "—",
        }

    cached_lines = len(ent.get("lines") or [])
    pos = int(ent.get("pos") or 0)
    size = int(ent.get("size") or 0)

    now_m = time.monotonic()
    last_m = float(ent.get("last_read_m") or 0.0)
    last_ts = float(ent.get("last_read_ts") or 0.0)

    # last_read label
    last_read_label = "—"
    last_read_ts_out = None
    if last_ts > 0:
        try:
            from datetime import datetime

            last_read_label = datetime.fromtimestamp(last_ts).strftime("%H:%M:%S")
            last_read_ts_out = last_ts
        except Exception:
            last_read_label = "—"
            last_read_ts_out = None

    # age label/state
    age_s = None
    age_state = "CACHE_EMPTY"
    age_label = "— (empty)"

    if last_m > 0:
        age_s = max(0.0, now_m - last_m)
        age_state = "OK"
        age_label = f"{int(age_s)}s"
    else:
        # last_read_m is bumped only when cache was updated with non-empty chunk or reset.
        # If file exists but we never appended anything, treat it as "cache empty".
        if cached_lines > 0:
            # defensive fallback (should not happen, but keep UX safe)
            age_state = "OK"
            age_label = "0s"

    return {
        "cached_lines": cached_lines,
        "pos": pos,
        "size": size,
        "age_s": age_s,
        "age_state": age_state,
        "age_label": age_label,
        "last_read_ts": last_read_ts_out,
        "last_read_label": last_read_label,
    }

    ent = _JSONL_TAIL_CACHE.get(key)
    if ent is None:
        return {
            "cached_lines": 0,
            "pos": 0,
            "size": 0,
            "age_s": None,
            "age_state": "NO_READ_YET",
            "age_label": "— (no read yet)",
        }

    cached_lines = len(ent.get("lines") or [])
    pos = int(ent.get("pos") or 0)
    size = int(ent.get("size") or 0)

    now_m = time.monotonic()
    last_m = float(ent.get("last_read_m") or 0.0)

    age_s = None
    age_state = "CACHE_EMPTY"
    age_label = "— (cache empty)"

    if last_m > 0:
        age_s = max(0.0, now_m - last_m)
        age_state = "OK"
        age_label = f"{int(age_s)}s"
    else:
        # last_read_m is bumped only when cache was updated with non-empty chunk or reset.
        # If file exists but we never appended anything, treat it as "cache empty".
        if cached_lines > 0:
            # defensive fallback (should not happen, but keep UX safe)
            age_state = "OK"
            age_label = "0s"

    return {
        "cached_lines": cached_lines,
        "pos": pos,
        "size": size,
        "age_s": age_s,
        "age_state": age_state,
        "age_label": age_label,
    }


def read_event_spine_tail(path, n: int):
    """
    Read last N events from events.jsonl (read-only).

    Best-effort parser:
    - tries JSON first (after trimming + BOM strip)
    - then tries ast.literal_eval for python-dict-like lines (single quotes)
    - falls back to raw truncated line

    Returns list[str] formatted as 'ts | type | message'.
    """
    if not path.exists():
        return ["events: unavailable"]

    # local import: keep UI-only helper resilient
    try:
        import json as _json  # type: ignore
    except Exception:
        _json = None  # type: ignore

    # Use cached tail reader to avoid re-reading the whole file on each refresh.
    tail = _read_jsonl_tail_lines(Path(path), max(50, int(n)))
    if not tail:
        return ["events: empty"]
    out = []

    def _norm_msg(v) -> str:
        try:
            if v is None:
                return ""
            if isinstance(v, (dict, list)):
                if _json is not None:
                    return _json.dumps(v, ensure_ascii=False)
                return str(v)
            return str(v)
        except Exception:
            return ""

    for ln in tail:
        ln_clean = (ln or "").strip().lstrip("\ufeff")
        if not ln_clean:
            continue

        obj = None

        # 1) strict-ish JSON
        try:
            if _json is not None:
                obj = _json.loads(ln_clean)
            else:
                obj = None
        except Exception:
            obj = None

        # 2) python-literal dict (single quotes, etc.) — best-effort
        if obj is None and ln_clean.startswith("{") and ":" in ln_clean:
            try:
                import ast  # local import: UI-only helper
                obj = ast.literal_eval(ln_clean)
            except Exception:
                obj = None

        if isinstance(obj, dict):
            ts = obj.get("ts") or obj.get("time") or obj.get("ts_utc") or "?"
            et = obj.get("type") or obj.get("event") or obj.get("kind") or "?"
            msg = obj.get("msg") or obj.get("message") or obj.get("text") or ""
            if (not msg) and isinstance(obj.get("payload"), dict):
                pl = obj.get("payload") or {}
                msg = pl.get("msg") or pl.get("message") or pl.get("text") or ""
                if not msg:
                    try:
                        if _json is not None:
                            msg = _json.dumps(pl, ensure_ascii=False)
                        else:
                            msg = str(pl)
                    except Exception:
                        msg = str(pl)
            msg = _norm_msg(msg).replace("\n", " ").strip()

            ts_s = _norm_msg(ts).replace("\n", " ").strip()
            et_s = _norm_msg(et).replace("\n", " ").strip()

            # keep it compact, never break UI
            if len(msg) > 140:
                msg = msg[:137] + "..."

            out.append(f"{ts_s} | {et_s} | {msg}")
        else:
            # raw fallback (compact)
            raw = ln_clean.replace("\n", " ").strip()
            if len(raw) > 180:
                raw = raw[:177] + "..."
            out.append(raw)

    return out or ["events: empty"]


def get_last_ui_read_only_block(ev_path: "Path", max_lines: int = 500):
    """
    UI-only helper: scan runtime/events.jsonl tail and return last UI_READ_ONLY_BLOCK as:
      {"action": str|None, "details": dict, "ts": float|None}
    """
    try:
        import json as _json  # local import for resilience
    except Exception:
        _json = None  # type: ignore

    # Use existing incremental tail reader (UI-only)
    try:
        lines = _read_jsonl_tail_lines(str(ev_path), max_lines=max_lines)
    except Exception:
        return None

    if not lines:
        return None

    for ln in reversed(lines):
        s = (ln or "").strip()
        if not s:
            continue
        if _json is None:
            continue
        try:
            obj = _json.loads(s)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get("type") != "UI_READ_ONLY_BLOCK":
            continue

        payload = obj.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}

        return {
            "action": payload.get("action"),
            "action_title": payload.get("action_title"),
            "details": payload.get("details") or {},
            "suppressed_count": payload.get("suppressed_count"),
            "suppression_window_s": payload.get("suppression_window_s"),
            "first_suppressed_ts": payload.get("first_suppressed_ts"),
            "last_suppressed_ts": payload.get("last_suppressed_ts"),
            "ts": obj.get("ts"),
        }

    return None


def format_trading_explainability(payload: dict) -> str:
    """
    UI read-only explainability for the START/STOP (AUTOSIM) button.

    States (read-only):
      1) AUTOSIM=OFF -> state=OFF (press START)
      2) AUTOSIM=ON  + blocked -> blocked=<reason>
      3) AUTOSIM=ON  + allowed -> allowed

    IMPORTANT:
    - MUST NOT change FSM/MODE/Gate/why_not.
    - This is display-only.
    """
    if not isinstance(payload, dict):
        payload = {}

    # UI-local indicators (do not affect backend)
    ui_mode = str(payload.get("_ui_mode") or "SIM").upper()
    autosim_on = bool(payload.get("_autosim_on", False))
    safe_on = bool(payload.get("_safe_on", False))
    dry_on = bool(payload.get("_dry_run_on", True))

    autosim = "AUTOSIM=ON" if autosim_on else "AUTOSIM=OFF"
    mode_part = f"UI_MODE={ui_mode}"
    safe_part = "SAFE=ON" if safe_on else "SAFE=OFF"
    dry_part = "DRY=ON" if dry_on else "DRY=OFF"

    # 1) If AUTOSIM is OFF: do not claim "allowed".
    if not autosim_on:
        return f"{autosim} | {mode_part} | {safe_part} | {dry_part} | state=OFF (press START)"

    # Determine block reason (read-only)
    why = payload.get("why_not") or []
    if not isinstance(why, list):
        why = []
    why = [str(x).strip() for x in why if str(x).strip()]

    gate_tag = format_gate_tag(payload.get("gate"))
    gate_veto = gate_tag.startswith("GATE=VETO")

    # MODE can be a policy limiter for auto-trading even if why_not is empty.
    mode_val = str(payload.get("mode") or "").upper()

    blocked = False
    block_head = ""

    if why:
        blocked = True
        block_head = why[0]
    elif gate_veto:
        blocked = True
        block_head = (
            gate_tag.replace("GATE=VETO:", "")
            .replace("GATE=VETO", "")
            .strip(":")
            or "GATE_VETO"
        )
    elif mode_val == "MANUAL_ONLY":
        blocked = True
        block_head = "MODE:MANUAL_ONLY"

    if blocked:
        return f"{autosim} | {mode_part} | {safe_part} | {dry_part} | blocked={block_head}"

    return f"{autosim} | {mode_part} | {safe_part} | {dry_part} | allowed"

def format_gate_line(gate):
    """
    UI-only helper (display-only).
    Returns a human line for notifications:
      - "Gate: ALLOW"
      - "Gate: VETO (MANUAL_STOP, HARD_STOP)"
    """
    if not isinstance(gate, dict) or not gate:
        return ""
    decision = str(gate.get("decision") or "").upper() or "N/A"
    if decision == "ALLOW":
        return "Gate: ALLOW"
    reasons = gate.get("reasons") or []
    if not isinstance(reasons, list):
        reasons = []
    if decision == "VETO":
        if reasons:
            return "Gate: VETO (" + ", ".join(str(x) for x in reasons[:2]) + ")"
        return "Gate: VETO"
    return f"Gate: {decision}"

class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title(APP_TITLE)
        self.configure(bg="#1c1f24")
        self.geometry("1120x640")
        self.minsize(980, 540)

        self.var_symbol = tk.StringVar(value=DEFAULT_SYMBOLS[0])
        self.var_qty = tk.StringVar(value="9")
        self.safe_on: bool = False
        self._mode: str = "SIM"

        # Контроллер режимов / SAFE / Dry-Run
        self.mode_controller = ModeController(self, SAFE_FILE)

        # Контроллер графиков (RSI / LIVE Chart)
        self.chart_controller = ChartController(self, ChartPanel)
        
        # Сервис снапшота ядра (equity + статус-бар + deals journal)
        self.snapshot_service = SnapshotService(self)

        # Контроллер панели активных позиций (Active position (SIM))
        # Важно: передаём только безопасный UIAPI-геттер,
        # чтобы не ломать изоляцию слоёв.
        self.positions_controller = PositionsController(
            app=self,
            uiapi_getter=self._ensure_uiapi,
        )

        # Контроллер AUTOSIM (ручное управление симулятором через UI)
        self.autosim_controller = AutosimController(
            app=self,
            ui_state=None,  # UIState подключим позже, когда начнём его реально использовать
            uiapi_getter=self._ensure_uiapi,
            save_sim_state_fn=self._save_sim_state_via_uiapi,
        )

        # TickUpdater — ранний TickService / Update Router для tick-снапшотов ядра.
        # Не имеет собственного цикла, живёт внутри SnapshotService/UIRefreshService.
        self.tick_updater = TickUpdater(self)

        # Подписываем UI-потребителей на EventBus (без дублей)
        install_default_ui_subscribers(self)

        # UI-флаг для Dry-Run бейджа (пока влияет только на внешний вид и логи)
        self.dry_run_ui_on: bool = True

        # настройки лога (ограничение длины и дешёвые обновления)
        self._log_max_lines: int = 3000
        self._log_trim_chunk: int = 500
        self._log_trim_every: int = 20
        self._log_lines_added: int = 0

        # кэш последнего текста для Active positions, чтобы не перерисовывать без нужды
        self._last_active_text: str = ""

        # состояние сигналов
        self._last_signal_side: Optional[str] = None

        # состояние авто-SIM
        self._autosim = None
        self._AUTOSIM_FACTORY = AUTOSIM_FACTORY
        self._sim_log_state = None  # (equity, open_positions)
        self._sim_symbol: Optional[str] = None
        # ссылка на виджет журнала сделок (для router-обновления)
        self._deals_journal_widget = None


        # Стили применяются через ui.layout.styles.apply_styles
        apply_styles(self, apply_neutral_dark)

        # STEP 1.4: toast notifications (non-blocking)
        self.toast = None
        try:
            if ToastManager is not None:
                self.toast = ToastManager(self)
        except Exception:
            self.toast = None

        # Topbar + paths: ui.layout.topbar
        create_topbar(self, DEFAULT_SYMBOLS)

        try:
            ctrl = getattr(self, "autosim_controller", None)
            if ctrl is not None and hasattr(ctrl, "bind_to_topbar"):
                ctrl.bind_to_topbar(self)
        except Exception as e:
            self._log(f"[AUTOSIM] bind failed: {e}")

        # v2.2.49 — Tabbed UI Shell (read-only)
        # Tabs are UI containers only. No side-effects, no trading controls.
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        tab_main = ttk.Frame(nb, style="Dark.TFrame")
        tab_portfolio = ttk.Frame(nb, style="Dark.TFrame")
        tab_chart = ttk.Frame(nb, style="Dark.TFrame")
        tab_strategies = ttk.Frame(nb, style="Dark.TFrame")
        tab_explain = ttk.Frame(nb, style="Dark.TFrame")
        tab_journal = ttk.Frame(nb, style="Dark.TFrame")
        tab_notifications = ttk.Frame(nb, style="Dark.TFrame")
        tab_settings = ttk.Frame(nb, style="Dark.TFrame")

        nb.add(tab_main, text="Main")
        nb.add(tab_portfolio, text="Portfolio")
        nb.add(tab_chart, text="Chart")
        nb.add(tab_strategies, text="Strategies")
        nb.add(tab_explain, text="Explain")
        nb.add(tab_journal, text="Journal")
        nb.add(tab_notifications, text="Notifications")
        nb.add(tab_settings, text="Settings")

        # Public handles (for later incremental wiring)
        self.nb = nb
        self.tab_main = tab_main
        self.tab_portfolio = tab_portfolio
        self.tab_chart = tab_chart
        self.tab_strategies = tab_strategies
        self.tab_explain = tab_explain
        self.tab_journal = tab_journal
        self.tab_notifications = tab_notifications
        self.tab_settings = tab_settings

        # v2.3.1 — Portfolio Dashboard (read-only)
        # Passive UI widget: updated via EventBus EVT_SNAPSHOT only.
        try:
            from ui.widgets.portfolio_dashboard import PortfolioDashboard

            dash = PortfolioDashboard(tab_portfolio)
            dash.frame.pack(fill="both", expand=True, padx=8, pady=8)
            self.portfolio_dashboard = dash
        except Exception as e:
            self.portfolio_dashboard = None
            ttk.Label(
                tab_portfolio,
                text=f"Portfolio Dashboard unavailable: {e}",
                style="Muted.TLabel",
            ).pack(anchor="w", padx=8, pady=8)

        # v2.3.6 — Notifications Panel (read-only)
        try:
            from ui.widgets.notifications_panel import NotificationsPanel

            np = NotificationsPanel(tab_notifications)
            np.frame.pack(fill="both", expand=True, padx=8, pady=8)
            self.notifications_panel = np
        except Exception as e:
            self.notifications_panel = None
            ttk.Label(
                tab_notifications,
                text=f"Notifications unavailable: {e}",
                style="Muted.TLabel",
            ).pack(anchor="w", padx=8, pady=8)

        # v2.3.1 — Portfolio Dashboard (read-only)
        # Passive UI widget: updated via EventBus EVT_SNAPSHOT only.
        try:
            from ui.widgets.portfolio_dashboard import PortfolioDashboard

            dash = PortfolioDashboard(tab_portfolio)
            dash.frame.pack(fill="both", expand=True, padx=8, pady=8)
            self.portfolio_dashboard = dash
        except Exception as e:
            self.portfolio_dashboard = None
            ttk.Label(
                tab_portfolio,
                text=f"Portfolio Dashboard unavailable: {e}",
                style="Muted.TLabel",
            ).pack(anchor="w", padx=8, pady=8)

        # Placeholders / mounts (read-only)
        from ui.strategy_registry import build_strategy_registry_tab
        build_strategy_registry_tab(self, tab_strategies, open_journal_cb=self._ui_deeplink_open_sim_journal)

        # apply pending focus (if any) after registry mount
        try:
            pending = str(getattr(self, "_strategy_focus_pending_sid", "") or "").strip()
            fn = getattr(self, "_strategy_registry_focus_sid", None)
            if pending and callable(fn):
                fn(pending)
                self._strategy_focus_pending_sid = ""
        except Exception:
            pass

        # Explain tab (read-only): show the same explain text as the top panel
        explain_frame = ttk.Frame(tab_explain)
        explain_frame.pack(fill="both", expand=True, padx=8, pady=8)

        ttk.Label(
            explain_frame,
            text="Explain (read-only) — WHY NOT / GATE LAST / SIM Decision Trace",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 6))

        explain_scroll = ttk.Scrollbar(explain_frame, orient="vertical")
        explain_scroll.pack(side="right", fill="y")

        self.explain_text = tk.Text(
            explain_frame,
            height=18,
            wrap="word",
            yscrollcommand=explain_scroll.set,
        )
        self.explain_text.pack(side="left", fill="both", expand=True)

        explain_scroll.config(command=self.explain_text.yview)

        # Make it read-only
        self.explain_text.configure(state="disabled")

        # Local cache to avoid flicker
        self._explain_tab_cache = ""

        ttk.Button(tab_journal, text="SIM Journal", style="Dark.TButton", command=self._cmd_open_sim_journal).pack(anchor="w", padx=8, pady=8)
        ttk.Label(tab_settings, text="Settings (read-only) — coming later", style="Muted.TLabel").pack(anchor="w", padx=8, pady=8)

        # Chart tab (chart-first): embedded LIVE Candles mount (UI-only)
        chart_mount = ttk.Frame(tab_chart, style="Dark.TFrame")
        chart_mount.pack(fill="both", expand=True, padx=8, pady=8)
        self._chart_mount = chart_mount  # used by ChartController embedded mode

        # small header row inside Chart tab (optional actions)
        chart_head = ttk.Frame(chart_mount, style="Dark.TFrame")
        chart_head.pack(fill="x", pady=(0, 6))

        ttk.Label(
            chart_head,
            text="Chart (read-only) — LIVE Candles / SAFE / STALE",
            style="Muted.TLabel",
        ).pack(side="left")

        ttk.Button(
            chart_head,
            text="Pop-out",
            style="Dark.TButton",
            command=self._open_candles_live_chart_popout,
        ).pack(side="right")

        # Панель активной позиции: ui.layout.positions_panel (goes to Main tab)
        create_positions_panel(self, parent=tab_main)

        # Лог-панель + StatusBar: ui.layout.deals_panel (goes to Main tab)
        create_deals_panel(self, StatusBar, parent=tab_main)

        # 1) автоподхват SIM-состояния (через runtime_state / UIAPI)
        self._load_sim_state_from_file()

        # 2) одноразовая инициализация UI из runtime_state (equity / meta)
        self._init_from_saved_state()

        # режим по умолчанию — SIM (через UIAPI)
        self._set_mode("SIM")
        
        # NEW: если UIAPI уже был создан, синхронизируем режим и там
        api = getattr(self, "_uiapi", None)
        if api is not None:
            try:
                api.set_mode("SIM")
            except Exception:
                pass

        self._log_diag_startup()

        self._refresh_safe_badge()

        # STEP1.3.1: цикл обновления UI вынесен в UIRefreshService
        self.refresh_service = UIRefreshService(self, interval_ms=1000)
        self.refresh_service.start()


    def _load_sim_state_from_file(self) -> None:
        """
        Пытаемся восстановить последний снимок SIM при старте UI.

        ВАЖНО:
        - UI больше не читает runtime/sim_state.json напрямую;
        - все обращения идут через UIAPI → core.runtime_state.load_runtime_state();
        - sim-состояние берётся из runtime-снапшота по ключу "sim".
        """
        # При активном PANIC авто-восстановление запрещено
        try:
            api = self._ensure_uiapi()
            if api is not None and hasattr(api, "is_panic_active") and api.is_panic_active():
                try:
                    self._log("[SIM] panic mode active, skip sim_state auto-recovery")
                except Exception:
                    pass
                return
        except Exception:
            return

        # Дальше работаем только через UIAPI / runtime_state
        try:
            uiapi = self._ensure_uiapi()
            if uiapi is None or not hasattr(uiapi, "get_runtime_state_snapshot"):
                # UIAPI недоступен — нечего восстанавливать
                return

            runtime_snapshot = uiapi.get_runtime_state_snapshot() or {}
        except Exception as e:  # noqa: BLE001
            try:
                self._log(f"[SIM] failed to load runtime_state snapshot: {e}")
            except Exception:
                pass
            return

        # Из объединённого runtime-состояния берём SIM-секцию.
        # Формат sim_state.json: { "ts": ..., "symbol": ..., "portfolio": {...}, "active": [...], ... }
        try:
            snapshot = runtime_snapshot.get("sim") or {}
        except Exception:
            snapshot = {}

        if not snapshot:
            # Нет sim-состояния — просто выходим
            return

        # Уже существующий метод, который красиво рисует таблицу Active position (SIM)
        try:
            self._update_active_from_sim(snapshot)
        except Exception:
            # Если формат снапшота изменился/битый — просто молча игнорируем
            # (UI не должен падать из-за проблем с runtime-файлами)
            pass

    def _init_from_saved_state(self) -> None:
        """
        Одноразовая инициализация UI из runtime_state через UIAPI.

        Цель:
        - аккуратно подхватить last-known equity / pnl из runtime/state.json,
          не читая файл напрямую;
        - обновить мини-панель Equity до первого снапшота StateEngine.

        Формат runtime_state (см. core/runtime_state.py):

            {
                "positions": {...},
                "meta": {...},
                "sim": {...}
            }

        Здесь мы используем только блок "meta": предполагается, что там
        находятся агрегированные метрики портфеля (equity, pnl_*).
        """
        # UI должен ходить только через UIAPI → runtime_state
        try:
            api = self._ensure_uiapi()
            if api is None or not hasattr(api, "get_runtime_state_snapshot"):
                return

            runtime_snapshot = api.get_runtime_state_snapshot() or {}
            if not isinstance(runtime_snapshot, dict):
                return
        except Exception:
            # Любые проблемы runtime_state не должны ломать старт UI
            return

        # Аккуратно достаём meta-блок
        try:
            meta = runtime_snapshot.get("meta") or {}
        except Exception:
            meta = {}

        if not isinstance(meta, dict) or not meta:
            # Нечего инициализировать
            return

        # Готовим "псевдо-снапшот" в формате, который ожидает _update_equity_bar:
        # snapshot["portfolio"] — словарь с equity / pnl_*.
        fake_snapshot = {"portfolio": dict(meta)}

        try:
            self._update_equity_bar(fake_snapshot)
        except Exception:
            # Мини-панель Equity — вспомогательный элемент, падать из-за неё нельзя
            return

    def _set_active_text(self, text: str) -> None:
        """
        Заполняет панель Active positions и подсвечивает:
        - pnl_pos / pnl_neg: PnL% (зелёный/красный)
        - side_long / side_short: колонка Side (LONG / SHORT)

        Формат строк задаётся _update_active_from_sim:
            header -> "Symbol Side Qty Entry Last Value Pnl% TP SL Hold Trend"
            далее строки с теми же колонками.
        """
        box = getattr(self, "active_box", None)
        if box is None:
            return

        # кэшируем последний текст, чтобы не перерисовывать панель без изменений
        new_text = text or ""
        try:
            last_text = getattr(self, "_last_active_text", "")
        except Exception:
            last_text = ""
        if new_text == last_text:
            return
        try:
            self._last_active_text = new_text
        except Exception:
            # если не удалось сохранить кэш — продолжаем без оптимизации
            pass

        lines = new_text.splitlines()

        try:
            box.configure(state="normal")
            box.delete("1.0", "end")

            if not lines:
                box.insert("end", "— no active positions —")
                box.configure(state="disabled")
                return

            # Пишем построчно, чтобы знать индексы для тегов
            for row_idx, line in enumerate(lines, start=1):
                box.insert(f"{row_idx}.0", line + ("\n" if row_idx < len(lines) else ""))

            # Если нет заголовка с 'Pnl%' — нечего раскрашивать
            if not any("Pnl%" in ln for ln in lines):
                box.configure(state="disabled")
                return

            # Начиная с 3-й строки (после header и разделителя) раскрашиваем Side и PnL
            for row_idx, line in enumerate(lines, start=1):
                if row_idx <= 2:
                    continue  # header + "----"

                try:
                    parts = line.split()
                    # 0:Symbol 1:Side 2:Qty 3:Entry 4:Last 5:Value 6:Pnl% ...
                except Exception:
                    continue

                # --- подсветка Side ---
                try:
                    side_token = parts[1]
                    side_u = side_token.upper()
                    side_tag = None
                    if side_u.startswith("LONG") or side_u.startswith("BUY"):
                        side_tag = "side_long"
                    elif side_u.startswith("SHORT") or side_u.startswith("SELL"):
                        side_tag = "side_short"

                    if side_tag:
                        col_start = line.find(side_token)
                        if col_start >= 0:
                            col_end = col_start + len(side_token)
                            try:
                                box.tag_add(
                                    side_tag,
                                    f"{row_idx}.{col_start}",
                                    f"{row_idx}.{col_end}",
                                )
                            except Exception:
                                pass
                except Exception:
                    pass

                # --- подсветка PnL% ---
                try:
                    pnl_token = parts[6]
                except Exception:
                    continue

                # чистим от процентов и плюсиков
                raw = pnl_token.replace("%", "").replace("+", "").strip()
                try:
                    pnl_val = float(raw)
                except Exception:
                    continue

                if pnl_val > 0.0:
                    tag = "pnl_pos"
                elif pnl_val < 0.0:
                    tag = "pnl_neg"
                else:
                    continue

                col_start = line.find(pnl_token)
                if col_start < 0:
                    continue
                col_end = col_start + len(pnl_token)

                try:
                    box.tag_add(
                        tag,
                        f"{row_idx}.{col_start}",
                        f"{row_idx}.{col_end}",
                    )
                except Exception:
                    pass
                # --- маркер тренда в последней колонке ---
                try:
                    trend_token = parts[-1]
                    col_start = line.rfind(trend_token)
                    if col_start >= 0:
                        col_end = col_start + len(trend_token)
                        if pnl_val > 0.0:
                            ttag = "trend_up"
                        elif pnl_val < 0.0:
                            ttag = "trend_down"
                        else:
                            ttag = "trend_flat"
                        try:
                            box.tag_add(
                                ttag,
                                f"{row_idx}.{col_start}",
                                f"{row_idx}.{col_end}",
                            )
                        except Exception:
                            pass
                except Exception:
                    pass

            box.configure(state="disabled")
        except tk.TclError:
            # окно/виджет уже уничтожено — игнорируем обновление панели
            return

    def _update_active_from_sim(self, snapshot: dict) -> None:
        """Delegates Active position panel update to PositionsController.

        Публичный API метода сохраняется (все вызовы внутри App продолжают
        использовать _update_active_from_sim), но сама логика вынесена
        в ui.controllers.positions_controller.PositionsController.
        """
        ctrl = getattr(self, "positions_controller", None)
        if ctrl is None:
            # Если контроллер по какой-то причине не создан —
            # просто не трогаем панель.
            return

        try:
            ctrl.update_from_snapshot(snapshot)
        except Exception:
            # панель активных позиций не должна ломать основной UI
            return

    def _update_equity_bar(self, snapshot: dict | None) -> None:
        """Обновляет мини-панель портфеля по snapshot['portfolio']."""
        me = getattr(self, "mini_equity", None)
        if me is None:
            return

        snapshot = snapshot or {}
        portfolio = snapshot.get("portfolio")
        if not isinstance(portfolio, dict):
            portfolio = {}

        try:
            me.update(portfolio)
        except Exception:
            # ошибки mini-панели не должны ломать основной UI
            return
            
    def _update_status_bar(self, snapshot: dict | None) -> None:
        """Обновляет StatusBar: режим и передаёт снапшот самому виджету."""
        # сначала пробуем обновить мини-панель портфеля
        try:
            self._update_equity_bar(snapshot)
        except Exception:
            pass

        sb = getattr(self, "status_bar", None)
        if sb is None:
            return

        snapshot = snapshot or {}

        # --- MODE ---
        try:
            mode = getattr(self, "_mode", "SIM") or "SIM"
            sb.set_mode(mode)
        except Exception:
            pass

        # остальное (health / lag / last deal) делегируем самому StatusBar
        try:
            # новый метод виджета, который умеет разбирать снапшот
            sb.update_from_snapshot(snapshot)
        except Exception:
            # статус-бар не должен ломать основной UI
            pass

        # --- HealthPanel update (UI isolation: snapshot-driven) ---
        try:
            hp = getattr(self, "health_panel", None)
            if hp is not None and hasattr(hp, "update_from_snapshot"):
                hp.update_from_snapshot(snapshot)
        except Exception:
            pass

    def _on_reset_sim(self) -> None:
        """Reset SIM engine (best-effort) and clear Active position."""
        try:
            # 1) Остановить AUTOSIM (если был включён)
            try:
                ctrl = getattr(self, "autosim_controller", None)
                if ctrl is not None and hasattr(ctrl, "stop"):
                    ctrl.stop()
                else:
                    # fallback: просто выключаем ссылку
                    self._autosim = None
            except Exception:
                self._autosim = None

            # 2) Сбросить локальные SIM-поля UI
            self._sim_log_state = None
            self._sim_symbol = None

            # 3) Попросить ядро сбросить SIM-состояние (UIAPI → core/runtime)
            try:
                api = self._ensure_uiapi()
                if api is not None and hasattr(api, "reset_sim_state"):
                    api.reset_sim_state()
            except Exception:
                # Reset SIM не должен ронять UI
                pass

            # 4) UI текст и лог
            self._set_active_text("— no active positions —")
            self._log("[SIM] reset requested")
        except Exception as e:
            try:
                self._log(f"[SIM] reset error: {e}")
            except Exception:
                pass

    def _autosim_call(self, method_name: str, log_tag: str) -> None:
        """Internal helper: proxy AUTOSIM calls to AutosimController."""
        try:
            ctrl = getattr(self, "autosim_controller", None)
            if ctrl is not None and hasattr(ctrl, method_name):
                getattr(ctrl, method_name)()
        except Exception as e:
            self._log(f"[AUTOSIM] {log_tag} failed: {e}")

    def _cmd_autosim_start(self) -> None:
        self._autosim_call("start", "start")

    def _cmd_autosim_stop(self) -> None:
        self._autosim_call("stop", "stop")

    def _cmd_autosim_toggle(self) -> None:
        """Proxy: делегирует toggle AUTOSIM контроллеру."""
        self._autosim_call("toggle", "toggle")

    def _log(self, line: str) -> None:
        """Добавляет строку в лог с ограничением длины и защитой от TclError."""
        text = (line or "").rstrip("\n")
        # не добавляем пустые строки
        if not text.strip():
            return

        try:
            self.log.insert("end", text + "\n")
            self.log.see("end")
        except tk.TclError:
            # окно уже уничтожено — игнорируем
            return

        # счётчик вставок, чтобы не считать строки каждый раз
        try:
            self._log_lines_added += 1
        except Exception:
            # на всякий случай инициализируем, если не успели в __init__
            self._log_lines_added = 1

        try:
            trim_every = int(getattr(self, "_log_trim_every", 20) or 0)
            max_lines = int(getattr(self, "_log_max_lines", 3000) or 0)
            trim_chunk = int(getattr(self, "_log_trim_chunk", 500) or 0)
        except Exception:
            trim_every, max_lines, trim_chunk = 20, 3000, 500

        if trim_every > 0 and max_lines > 0 and trim_chunk > 0:
            if self._log_lines_added % trim_every == 0:
                # мягкая проверка длины лога
                try:
                    end_index = self.log.index("end-1c")
                    num_lines = int(str(end_index).split(".")[0])
                except Exception:
                    num_lines = 0

                if num_lines > max_lines:
                    try:
                        self.log.delete("1.0", f"{trim_chunk}.0")
                    except tk.TclError:
                        # если виджет уже уничтожен — просто выходим
                        return

    def clear_log(self) -> None:
        """Полная очистка лога с мягким сбросом счётчика."""
        try:
            self.log.delete("1.0", "end")
        except tk.TclError:
            return
        except Exception:
            # другие ошибки тоже не должны ломать UI
            return
        # сбрасываем счётчик вставок
        try:
            self._log_lines_added = 0
        except Exception:
            pass

    def _safe_is_on(self) -> bool:
        """Proxy: делегирует проверку SAFE контроллеру режима."""
        return self.mode_controller.safe_is_on()

    def _refresh_safe_badge(self) -> None:
        self.mode_controller.refresh_safe_badge()

    def _toggle_safe(self) -> None:
        """Proxy: переключение SAFE_MODE через контроллер режима."""
        self.mode_controller.toggle_safe()

    def _refresh_dry_badge(self) -> None:
        self.mode_controller.refresh_dry_badge()

    def _toggle_dry(self) -> None:
        self.mode_controller.toggle_dry()

    def _set_mode(self, mode: str) -> None:
        self.mode_controller.set_mode(mode)

    def _toggle_mode(self) -> None:
        self.mode_controller.toggle_mode()

    def _set_status(self, text: str) -> None:
        self.title(f"{APP_TITLE} — {text}" if text else APP_TITLE)

    def _log_diag_startup(self) -> None:
        self._log(f"[DIAG] python={sys.executable}")

        def _diag_optional(obj, err, none_msg: str, err_prefix: str, ok_msg):
            """
            ok_msg: либо строка, либо callable(obj)->str
            Логи должны остаться по смыслу и порядку прежними.
            """
            if obj is None:
                self._log(none_msg)
                if err is not None:
                    self._log(f"{err_prefix}: {err!r}")
            else:
                if callable(ok_msg):
                    self._log(ok_msg(obj))
                else:
                    self._log(ok_msg)

        # ChartPanel
        _diag_optional(
            ChartPanel,
            _CHART_ERR,
            "[DIAG] ChartPanel=None",
            "[DIAG] ChartPanel import error",
            lambda obj: f"[DIAG] ChartPanel={obj}",
        )

        # ui_api diagnostics (оставляем try/except как раньше)
        try:
            _diag_optional(
                UIAPI,
                _UI_ERR,
                "[DIAG] ui_api unavailable (core.ui_api.UIAPI not imported)",
                "[DIAG] ui_api import error",
                "[DIAG] ui_api OK (core.ui_api.UIAPI)",
            )
        except Exception:
            pass

        # matplotlib diagnostics (оставляем как было)
        try:
            import matplotlib  # type: ignore

            self._log(f"[DIAG] matplotlib={matplotlib.__version__}")
        except Exception:
            self._log("[DIAG] matplotlib not available")

        # indicators / signals / advisor
        _diag_optional(
            INDICATORS,
            _IND_ERR,
            "[DIAG] indicators not available (core.indicators)",
            "[DIAG] indicators import error",
            "[DIAG] indicators OK (core.indicators)",
        )

        _diag_optional(
            SIGNALS,
            _SIG_ERR,
            "[DIAG] signals not available (core.signals)",
            "[DIAG] signals import error",
            "[DIAG] signals OK (core.signals)",
        )

        _diag_optional(
            ADVISOR,
            _ADV_ERR,
            "[DIAG] advisor not available (core.advisor)",
            "[DIAG] advisor import error",
            "[DIAG] advisor OK (core.advisor)",
        )

    # ----------------------------------------------------- periodic tasks --

    def _periodic_refresh(self) -> None:
        """Proxy: делегирует периодический рефреш сервису UIRefreshService.

        Оставлен для обратной совместимости: старый код может вызывать
        _periodic_refresh напрямую.
        """
        # Если по какой-то причине сервис ещё не создан или остановлен,
        # безопасно выходим.
        svc = getattr(self, "refresh_service", None)
        if svc is None:
            return
        svc.periodic_refresh()
  
    def _push_current_symbol_to_uiapi(self) -> None:
        """Отправить текущий символ из UI в UIAPI."""
        try:
            api = self._ensure_uiapi()
            if api is None or not hasattr(api, "set_current_symbol"):
                return
            sym = ""
            try:
                sym = self.var_symbol.get().strip()
            except Exception:
                pass
            api.set_current_symbol(sym)
        except Exception:
            # не ломаем UI, если что-то пошло не так
            pass

    def _refresh_from_core_snapshot(self) -> None:
        """Proxy: обновление мини-панелей из снапшота ядра через SnapshotService."""
        svc = getattr(self, "snapshot_service", None)
        if svc is None:
            return
        svc.refresh_from_core_snapshot()

        # SAFE badge/policy is snapshot-driven (core-owned)
        try:
            self._refresh_safe_badge()
        except Exception:
            pass
        # Trading FSM + policy badge (read-only)
        try:
            self._refresh_trading_status_badge()
        except Exception:
            pass

        # Explain tab sync (read-only)
        try:
            self._sync_explain_tab()
        except Exception:
            pass

    def _refresh_trading_status_badge(self) -> None:
        api = self._ensure_uiapi()
        if api is None or not hasattr(api, "get_trading_status"):
            try:
                if hasattr(self, "var_trade_status"):
                    self.var_trade_status.set("FSM=UNKNOWN | MODE=UNKNOWN | ERR=uiapi_missing")
            except Exception:
                pass
            try:
                if hasattr(self, "var_trade_explain"):
                    self.var_trade_explain.set("AUTOSIM: unknown | UI_MODE=UNKNOWN | SAFE=? | DRY=? | blocked=uiapi_missing")
            except Exception:
                pass
            try:
                if hasattr(self, "var_explain_panel"):
                    self.var_explain_panel.set("")
            except Exception:
                pass
            return
        try:
            payload = api.get_trading_status() or {}
        except Exception:
            payload = {}

        if not isinstance(payload, dict):
            payload = {}
        # UI-only indicators for explainability (read-only)
        try:
            payload["_ui_mode"] = str(getattr(self, "_mode", "SIM") or "SIM").upper()
        except Exception:
            payload["_ui_mode"] = "SIM"
        try:
            payload["_autosim_on"] = bool(getattr(self, "_autosim", None) is not None)
        except Exception:
            payload["_autosim_on"] = False
        try:
            payload["_safe_on"] = bool(getattr(self, "safe_on", False))
        except Exception:
            payload["_safe_on"] = False
        try:
            payload["_dry_run_on"] = bool(getattr(self, "dry_run_ui_on", True))
        except Exception:
            payload["_dry_run_on"] = True

        err = payload.get("error")

        # UI is a dumb renderer: never prints "unavailable", never rewrites MODE.
        state = payload.get("state") or "UNKNOWN"
        mode = str(payload.get("mode") or "UNKNOWN").upper()

        # Freshness (read-only): prefer ts_utc, fallback to ts (epoch seconds)
        age_part = ""
        try:
            import time
            ts_utc = payload.get("ts_utc")
            ts_epoch = payload.get("ts")

            age_sec = None
            if ts_utc:
                try:
                    from datetime import datetime, timezone
                    ts_dt = datetime.fromisoformat(str(ts_utc).replace("Z", "+00:00"))
                    age_sec = int((datetime.now(timezone.utc) - ts_dt).total_seconds())
                except Exception:
                    age_sec = None
            elif ts_epoch is not None:
                try:
                    age_sec = int(time.time() - float(ts_epoch))
                except Exception:
                    age_sec = None

            if age_sec is not None and age_sec >= 0:
                if age_sec >= STALE_STATUS_AGE_SEC:
                    age_part = f" | age={age_sec}s | STALE"
                else:
                    age_part = f" | age={age_sec}s"
            else:
                age_part = " | age=unknown"
        except Exception:
            age_part = " | age=unknown"

        why = payload.get("why_not") or []
        txt_reason = format_why_not(why)
        reason = f" | {txt_reason[:48]}" if txt_reason else ""

        gate_tag = format_gate_tag(payload.get("gate"))
        gate_part = f" | {gate_tag}" if gate_tag else ""

        err_part = ""
        if err:
            s = str(err).replace("\n", " ").strip()
            if s:
                err_part = f" | ERR={s[:64]}"

        txt = f"FSM={state} | MODE={mode}{age_part}{reason}{gate_part}{err_part}"

        # UI Read-Only feedback loop: show last UIAPI block in status + log once (no spam)
        try:
            blk = get_last_ui_read_only_block(EVENTS_JSONL_PATH, max_lines=500)
        except Exception:
            blk = None

        if isinstance(blk, dict) and blk.get("action"):
            # expose to Explain Panel formatter (UI-only)
            try:
                payload["_ui_read_only_block"] = blk
            except Exception:
                pass

            try:
                txt = f"{txt} | ui_block={blk.get('action')}"
            except Exception:
                pass

            try:
                import json as _json
                now_ts = time.time()

                action = blk.get("action")
                details = blk.get("details")

                # Stable signature: do NOT include event ts (it changes constantly)
                try:
                    details_s = _json.dumps(details, ensure_ascii=False, sort_keys=True)
                except Exception:
                    details_s = str(details)

                sig = f"{action}|{details_s}"

                last_sig = getattr(self, "_last_ui_block_sig", None)
                last_log_ts = getattr(self, "_last_ui_block_log_ts", 0.0)

                # Log immediately if new signature; otherwise apply cooldown
                cooldown_s = 5.0
                should_log = (sig != last_sig) or ((now_ts - float(last_log_ts)) >= cooldown_s)

                if should_log:
                    self._last_ui_block_sig = sig
                    self._last_ui_block_log_ts = now_ts
                    self._log(f"[UI][READ_ONLY_BLOCK] action={action} details={details}")
            except Exception:
                pass

        try:
            if hasattr(self, "var_trade_status"):
                self.var_trade_status.set(txt)
        except Exception:
            pass
        # Explainability line for START/STOP (AUTOSIM) + SIM/REAL + SAFE (read-only)
        try:
            if hasattr(self, "var_trade_explain"):
                self.var_trade_explain.set(format_trading_explainability(payload))
        except Exception:
            pass

        # Explain Panel (read-only): WHY_NOT + GATE_LAST
        try:
            if hasattr(self, "var_explain_panel"):
                self.var_explain_panel.set(format_explain_panel(payload))
        except Exception:
            pass

        # Control surface locks (UI-only): in MANUAL_ONLY disable trading controls
        try:
            self._apply_read_only_control_locks(payload)
        except Exception:
            pass

        # Event spine peek (read-only) — Text + count + optional autoscroll
        try:
            tail = read_event_spine_tail(EVENTS_JSONL_PATH, EVENT_SPINE_PEEK_N)
            n = len(tail)

            if hasattr(self, "var_events_count"):
                try:
                    self.var_events_count.set(f"({n})")
                except Exception:
                    pass

            txt_events = getattr(self, "txt_events", None)
            collapsed = bool(getattr(self, "_events_collapsed", False))
            autoscroll = bool(getattr(self, "_events_autoscroll", False))
            suppressed = bool(getattr(self, "_events_suppressed", False))

            if txt_events is not None:
                if not collapsed and not suppressed:
                    try:
                        txt_events.configure(state="normal")
                    except Exception:
                        pass
                    try:
                        txt_events.delete("1.0", "end")
                        txt_events.insert("end", "\n".join(tail))
                        if autoscroll:
                            txt_events.see("end")
                    except Exception:
                        pass
                    try:
                        txt_events.configure(state="disabled")
                    except Exception:
                        pass
            else:
                if hasattr(self, "var_event_spine"):
                    self.var_event_spine.set("events:\n" + "\n".join(tail))
        except Exception:
            # robust fallback: never fail UI refresh
            try:
                txt_events = getattr(self, "txt_events", None)
                if txt_events is not None:
                    try:
                        txt_events.configure(state="normal")
                    except Exception:
                        pass
                    try:
                        txt_events.delete("1.0", "end")
                        txt_events.insert("end", "events: unavailable")
                    except Exception:
                        pass
                    try:
                        txt_events.configure(state="disabled")
                    except Exception:
                        pass
                else:
                    self.var_event_spine.set("events: unavailable")
            except Exception:
                pass

    def _sync_explain_tab(self) -> None:
        """
        UI-only: mirror the top explain panel text into the Explain tab.
        No side-effects; never touches core.
        """
        if not hasattr(self, "explain_text"):
            return
        try:
            text = ""
            if hasattr(self, "var_explain_panel"):
                try:
                    text = str(self.var_explain_panel.get() or "")
                except Exception:
                    text = ""
            text = text.strip()

            prev = getattr(self, "_explain_tab_cache", "")
            if text == prev:
                return

            self._explain_tab_cache = text

            w = self.explain_text
            w.configure(state="normal")
            w.delete("1.0", "end")
            if text:
                w.insert("1.0", text)
            w.configure(state="disabled")
        except Exception:
            # never break UI
            return

    def _apply_read_only_control_locks(self, payload: dict) -> None:
        """
        UI-only: visually lock trading controls when system is MANUAL_ONLY.
        No core calls, no side-effects, just widget state/clickability.
        """
        if not isinstance(payload, dict):
            payload = {}

        mode = str(payload.get("mode") or "").upper().strip()
        why = payload.get("why_not") or []
        try:
            why_list = [str(x) for x in why] if isinstance(why, list) else []
        except Exception:
            why_list = []

        hard_stop = bool(payload.get("policy_hard_stop_active", False))

        # Lock criteria: MANUAL_ONLY OR explicit why_not OR hard stop
        locked = (
            mode == "MANUAL_ONLY"
            or ("MODE_MANUAL_ONLY" in why_list)
            or hard_stop
            or ("MANUAL_STOP" in why_list)
        )

        # --- buttons: BUY / Close / Panic ---
        for attr in ("btn_buy", "btn_close", "btn_panic"):
            w = getattr(self, attr, None)
            if w is None:
                continue
            try:
                w.configure(state=("disabled" if locked else "normal"))
            except Exception:
                pass

        # --- mode button ---
        w_mode = getattr(self, "btn_mode", None)
        if w_mode is not None:
            try:
                w_mode.configure(state=("disabled" if locked else "normal"))
            except Exception:
                pass

        # --- qty entry: de-emphasize “position sizing” in MANUAL_ONLY ---
        w_qty = getattr(self, "entry_qty", None)
        if w_qty is not None:
            try:
                w_qty.configure(state=("disabled" if locked else "normal"))
            except Exception:
                pass

        # --- SAFE / Dry-Run badges are labels: disable click by unbinding ---
        def _lock_badge(label_attr: str, toggle_attr: str) -> None:
            w = getattr(self, label_attr, None)
            if w is None:
                return
            try:
                # Always remove any previous click handler first to avoid stacking binds
                w.unbind("<Button-1>")
            except Exception:
                pass

            if locked:
                try:
                    w.configure(cursor="arrow")
                except Exception:
                    pass
                return

            # unlocked: restore click if toggle exists
            if hasattr(self, toggle_attr):
                try:
                    w.configure(cursor="hand2")
                except Exception:
                    pass
                try:
                    w.bind("<Button-1>", lambda e: getattr(self, toggle_attr)())
                except Exception:
                    pass

        _lock_badge("badge_safe", "_toggle_safe")
        _lock_badge("badge_dry", "_toggle_dry")

    # ----------------------------------------------------- indicators I/O --
    def _load_chart_prices(self, max_points: int = 300) -> Tuple[List[int], List[float]]:
        sym = self.var_symbol.get().strip() or DEFAULT_SYMBOLS[0]
        times: List[int] = []
        prices: List[float] = []

        # лёгкий bootstrap: если поток тиков пустой или короткий, попробуем подкачать историю с Binance
        boot_created = 0
        try:
            boot_created = ensure_ticks_bootstrap(sym, max_points=max_points, min_points=50)
        except Exception:
            boot_created = 0
        if boot_created > 0:
            try:
                self._log(f"[BOOTSTRAP] seeded {boot_created} ticks for {sym} from Binance REST")
            except Exception:
                pass
        # series via UIAPI (core-owned runtime I/O)
        try:
            api = self._ensure_uiapi()
            if api is not None and hasattr(api, "get_tick_series"):
                return api.get_tick_series(sym, max_points=max_points)
        except Exception:
            prices = []
            times = []
        return times, prices

    def _load_chart_ohlc(
        self,
        timeframe_s: int,
        *,
        max_candles: int = 300,
        max_ticks: int = 5000,
    ) -> dict:
        sym = self.var_symbol.get().strip() or DEFAULT_SYMBOLS[0]

        # лёгкий bootstrap: если поток тиков пустой/короткий, попробуем подкачать историю
        try:
            ensure_ticks_bootstrap(sym, max_points=max(300, int(max_candles) * 5), min_points=50)
        except Exception:
            pass

        try:
            api = self._ensure_uiapi()
            if api is not None and hasattr(api, "get_ohlc_series"):
                return api.get_ohlc_series(
                    sym,
                    int(timeframe_s),
                    max_candles=int(max_candles),
                    max_ticks=int(max_ticks),
                )
        except Exception:
            pass

        return {
            "symbol": (sym or "").upper(),
            "timeframe_s": int(timeframe_s or 0),
            "source": "runtime/ticks_stream.jsonl",
            "last_tick_ts_ms": None,
            "candles": [],
            "reason": "READ_FAILED",
        }

    def _compute_last_indicators(
        self, prices: List[float]
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        if INDICATORS is None or len(prices) < 30:
            return None, None, None

        try:
            rsi_vals = INDICATORS.rsi(prices, period=14)
            macd_vals, signal_vals = INDICATORS.macd(prices)
            if not rsi_vals or not macd_vals or not signal_vals:
                return None, None, None
            return rsi_vals[-1], macd_vals[-1], signal_vals[-1]
        except Exception as e:  # noqa: BLE001
            self._log(f"[DIAG] indicators error: {e!r}")
            return None, None, None


    def _refresh_indicators_and_signal(self) -> None:
        """Recompute indicators, signal, advisor and SIM snapshot."""
        last_snapshot: dict | None = None
        times, prices = self._load_chart_prices(max_points=300)
        # синхронизируем текущий символ с UIAPI
        self._push_current_symbol_to_uiapi()
        rsi_last, macd_last, macd_signal_last = self._compute_last_indicators(prices)

        # --- update RSI / MACD labels ---
        if rsi_last is None:
            self.label_rsi.configure(text="RSI: n/a")
        else:
            self.label_rsi.configure(text=f"RSI: {rsi_last:4.1f}")

        if macd_last is None or macd_signal_last is None:
            self.label_macd.configure(text="MACD: n/a")
        else:
            self.label_macd.configure(text=f"MACD: {macd_last:+.4f}")

        # --- compute EMA20 / EMA50 for filters ---
        ema_fast_last = None
        ema_slow_last = None
        price_last = None

        if prices:
            try:
                price_last = float(prices[-1])
            except Exception:
                price_last = None

        if INDICATORS is not None and prices:
            try:
                ema_fast_series = INDICATORS.ema(prices, period=20)
                ema_slow_series = INDICATORS.ema(prices, period=50)
                if ema_fast_series:
                    ema_fast_last = float(ema_fast_series[-1])
                if ema_slow_series:
                    ema_slow_last = float(ema_slow_series[-1])
            except Exception as e:  # noqa: BLE001
                self._log(f"[DIAG] EMA error: {e!r}")

        # --- reset signal / recommendation labels ---
        try:
            self.label_signal.configure(text="Signal: n/a")
        except Exception:
            pass
        try:
            self.label_reco.configure(text="Recommendation: n/a")
        except Exception:
            pass

        if SIGNALS is None or rsi_last is None:
            return

        # --- base RSI+MACD signal ---
        try:
            sym = (self.var_symbol.get() or "").strip()
        except Exception:
            sym = ""
        sig = SIGNALS.simple_rsi_macd_signal(
            rsi_last,
            macd_last,
            macd_signal_last,
            symbol=sym,
            ema_fast_last=ema_fast_last,
            ema_slow_last=ema_slow_last,
            price_last=price_last,
        )
        if sig is None:
            return

        d = sig.as_dict()
        strength = float(d.get("strength", 0.0) or 0.0)

        # --- signal label text ---
        label_text = f"Signal: {d.get('side', 'n/a')}"
        if strength > 0.0:
            label_text += f" [{strength:.2f}]"
        reason = d.get("reason") or ""
        if reason:
            label_text += f" ({reason})"
        try:
            self.label_signal.configure(text=label_text)
        except Exception:
            pass

        # --- LastSig mini-panel (signal-level summary) ---
        try:
            side = str(d.get("side", "n/a")).upper()
            arrow = "•"
            if side == "BUY":
                arrow = "↑"
            elif side == "SELL":
                arrow = "↓"
            last_sig_text = f"LastSig: {side} {arrow}"
            if strength > 0.0:
                last_sig_text += f"  strength={strength:.2f}"
            reason = d.get("reason") or ""
            if reason:
                last_sig_text += f"  {reason}"
            if getattr(self, "label_last_sig", None) is not None:
                self.label_last_sig.configure(text=last_sig_text)
        except Exception:
            pass

        # --- advisor recommendation (сначала посчитаем reco!) ---
        reco = None
        if ADVISOR is not None:
            try:
                reco = ADVISOR.compute_recommendation(
                    d.get("side", "HOLD"),
                    d.get("rsi"),
                    d.get("macd"),
                    d.get("macd_signal"),
                    prices,
                )
                r_side = str(reco.get("side", "HOLD"))
                r_strength = float(reco.get("strength", 0.0))
                r_reason = reco.get("reason", "")
                arrow = "•"
                if r_side == "BUY":
                    arrow = "↑"
                elif r_side == "SELL":
                    arrow = "↓"
                # компактный текст рекомендации для шапки
                text = f"Rec: {r_side} {arrow} {r_strength:.2f}"

                scout_note = None
                try:
                    scout_note = reco.get("scout_note") if isinstance(reco, dict) else None
                except Exception:
                    scout_note = None

                if isinstance(scout_note, dict):
                    try:
                        prio = scout_note.get("priority")
                        ts = scout_note.get("ts")

                        age_s = None
                        if isinstance(ts, (int, float)):
                            age_s = int(time.time() - ts)

                        parts = []
                        if prio:
                            parts.append(str(prio))
                        if age_s is not None:
                            parts.append(f"{age_s}s")

                        if parts:
                            text += " [" + " ".join(parts) + "]"

                        reason_sn = scout_note.get("reason")
                        if reason_sn:
                            short_reason = str(reason_sn)
                            if len(short_reason) > 40:
                                short_reason = short_reason[:37] + "..."
                            text += f" | {short_reason}"
                    except Exception:
                        pass
                else:
                    if r_reason:
                        short_reason = str(r_reason)
                        if len(short_reason) > 40:
                            short_reason = short_reason[:37] + "..."
                        text += f" | {short_reason}"

                try:
                    self.label_reco.configure(text=text)
                except Exception:
                    pass
                # NEW: передаём сигнал + рекомендацию + тренд в ядро (UIAPI)
                try:
                    api = self._ensure_uiapi()
                    if api is not None and hasattr(api, "update_advisor_snapshot"):
                        # d — это dict со side/rsi/macd/macd_signal, дополним symbol
                        meta = dict(d)
                        try:
                            meta["symbol"] = (self.var_symbol.get() or "").upper()
                        except Exception:
                            pass
                        api.update_advisor_snapshot(sig, reco, meta)
                except Exception:
                    # любые проблемы с ядром не должны ломать UI
                    pass
                    
            except Exception:
                reco = None

        # --- log + append to signal history buffer only when side changes ---
        if sig.side != self._last_signal_side:
            self._last_signal_side = sig.side
            self._log(
                "[SIGNAL] side={side} rsi={rsi:.1f} macd={macd:+.4f} "
                "macd_sig={macd_signal:+.4f} reason={reason}".format(**d)
            )
            try:
                if prices:
                    last_idx = len(prices) - 1
                else:
                    last_idx = None

                def _f(x, default=0.0):
                    try:
                        if x is None:
                            return float(default)
                        return float(x)
                    except Exception:
                        return float(default)

                def _s(x):
                    try:
                        return str(x) if x is not None else ""
                    except Exception:
                        return ""

                rec = {
                    "ts": int(time.time()),
                    "symbol": (self.var_symbol.get() or "").upper(),
                    "index": last_idx,
                    "side": _s(d.get("side")),
                    "rsi": _f(d.get("rsi"), 0.0),
                    "macd": _f(d.get("macd"), 0.0),
                    "macd_signal": _f(d.get("macd_signal"), 0.0),
                    "reason": _s(d.get("reason")),
                    "signal_strength": _f(d.get("strength", 0.0), 0.0),
}
                # если есть рекомендация — добавляем поля advisor’а
                if isinstance(reco, dict):
                    rec["recommendation_side"] = str(reco.get("side", "HOLD"))
                    rec["recommendation_strength"] = float(
                        reco.get("strength", 0.0) or 0.0
                    )
                    rec["recommendation_trend"] = str(reco.get("trend", "FLAT"))
                    rec["recommendation_score"] = float(
                        reco.get(
                            "score",
                            rec.get("recommendation_strength", 0.0),
                        )
                        or 0.0
                    )
                if isinstance(reco, dict) and isinstance(reco.get("scout_note"), dict):
                    rec["scout_note"] = reco.get("scout_note")

                # --- NEW 1.2.1: ReplaceLogic decision ---
                try:
                # -------------------------------------------------------------------
                # STEP 1.x NOTICE:
                # ReplaceLogic здесь используется ТОЛЬКО для наблюдательного "label"
                # и UX-подсказки (Scout/Note-style), НЕ для торговых решений и НЕ для исполнения.
                # Никакие REAL действия из этого блока не инициируются.
                # -------------------------------------------------------------------
                    api_rl = self._ensure_uiapi()
                    if (
                        api_rl is not None
                        and hasattr(api_rl, "decide_replace_from_signal_and_reco")
                    ):
                        decision = api_rl.decide_replace_from_signal_and_reco(d, reco)
                    else:
                        decision = None

                    if decision is not None:
                        rec["action"] = decision.action
                        rec["decision_side"] = decision.side
                        rec["decision_confidence"] = float(
                            getattr(decision, "confidence", 0.0) or 0.0
                        )
                        rec["decision_reason"] = str(getattr(decision, "reason", ""))

                except Exception:
                    # Любые ошибки ReplaceLogic не должны ломать UI
                    pass

                # NEW: добавляем сигнал в буфер UIAPI (recent_signals)
                try:
                    api2 = self._ensure_uiapi()
                    if api2 is not None and hasattr(api2, "append_recent_signal"):
                        api2.append_recent_signal(rec)
                    # core-owned persistence (UI must not write signals.jsonl directly)
                    if api2 is not None and hasattr(api2, "persist_signal_record"):
                        api2.persist_signal_record(rec)
                except Exception:
                    pass
            except Exception:
                pass

        # --- auto-SIM: shadow execution from signal + recommendation ---
        if self._autosim is not None and prices and reco is not None:
            try:
                symbol = (self.var_symbol.get() or "").upper()

                # reset SIM if user changed symbol
                if self._sim_symbol is not None and symbol != self._sim_symbol:
                    try:
                        self._on_reset_sim()
                    except Exception:
                        pass
                self._sim_symbol = symbol

                last_price = float(prices[-1])
                
                # NEW: пробрасываем последний тик в UIAPI/StateEngine
                try:
                    api = self._ensure_uiapi()
                    if api is not None and hasattr(api, "on_price"):
                        api.on_price(symbol, last_price)
                except Exception:
                    # любые проблемы с ядром не должны ломать AUTOSIM
                    pass

                snapshot = self._autosim.process(
                    symbol=symbol,
                    last_price=last_price,
                    simple_signal=sig,
                    recommendation=reco,
                )
                last_snapshot = snapshot
                # === LOG AUTOSIM TRADES via UIAPI (core-owned) ===
                try:
                    trades = snapshot.get("trades") or []
                    if trades:
                        api2 = self._ensure_uiapi()
                        for tr in trades:
                            rec = {
                                "type": "ORDER",
                                "mode": "SIM",
                                "symbol": tr.get("symbol"),
                                "side": tr.get("side"),
                                "qty": tr.get("qty"),
                                "price": tr.get("price"),
                                "status": tr.get("status", "FILLED"),
                                "ts": tr.get("ts", int(time.time())),
                                "source": "AUTOSIM",
                            }
                            if "pnl_cash" in tr:
                                rec["pnl_cash"] = tr.get("pnl_cash")
                            if "pnl_pct" in tr:
                                rec["pnl_pct"] = tr.get("pnl_pct")
                            if "reason" in tr:
                                rec["reason"] = tr.get("reason")
                            if "hold_seconds" in tr:
                                rec["hold_seconds"] = tr.get("hold_seconds")

                            # core-owned persistence
                            if api2 is not None and hasattr(api2, "persist_trade_record"):
                                api2.persist_trade_record(rec)

                            # keep UI buffer update (existing behavior)
                            try:
                                if api2 is not None and hasattr(api2, "append_recent_trade"):
                                    ts_val = rec.get("ts")
                                    if isinstance(ts_val, (int, float)):
                                        try:
                                            time_str = time.strftime(
                                                "%Y-%m-%d %H:%M:%S",
                                                time.localtime(ts_val),
                                            )
                                        except Exception:
                                            time_str = str(ts_val)
                                    else:
                                        time_str = str(ts_val or "")

                                    row = {
                                        "time": time_str,
                                        "symbol": rec.get("symbol"),
                                        "tier": "-",
                                        "action": rec.get("side") or rec.get("status") or "",
                                        "tp": None,
                                        "sl": None,
                                        "pnl_pct": rec.get("pnl_pct"),
                                        "pnl_abs": rec.get("pnl_cash"),
                                        "qty": rec.get("qty"),
                                        "entry": None,
                                        "exit": rec.get("price"),
                                    }
                                    api2.append_recent_trade(row)
                            except Exception:
                                pass
                except Exception as e:
                    self._log(f"[AUTOSIM] persist trades via UIAPI error: {e}")

                # persist snapshot for debug / future UI (атомарно)
                try:
                    self._save_sim_state_via_uiapi(snapshot)
                except Exception:
                    pass

                # update Active position panel + equity bar
                try:
                    self._update_active_from_sim(snapshot)
                    self._update_equity_bar(snapshot)
                except Exception:
                    pass

                # debounced SIM log: only when changed
                portfolio = snapshot.get("portfolio") or {}
                eq = portfolio.get("equity")
                open_cnt = portfolio.get("open_positions_count")
                if eq is not None and open_cnt is not None:
                    should_log = False
                    try:
                        eq_f = float(eq)
                        open_i = int(open_cnt)
                        prev = self._sim_log_state
                        if prev is None:
                            should_log = True
                        else:
                            prev_eq, prev_open = prev
                            if int(prev_open) != open_i:
                                should_log = True
                            elif abs(eq_f - float(prev_eq)) >= 0.1:
                                should_log = True
                    except Exception:
                        should_log = True
                    if should_log:
                        self._log(f"[SIM] equity={float(eq):.2f} open_positions={open_cnt}")
                        # v2.3.4 — UI is strictly READ-ONLY.
                        # Do NOT attempt to persist equity history from UI.
                        # PortfolioDashboard builds in-memory series from snapshots and can optionally
                        # preload from runtime/equity_history.csv if it exists (written by non-UI runtime).

                        # StatusBar + Mini-Equity обновляются через EVT_SNAPSHOT (ui/events/subscribers.py)
            except Exception as e:
                self._log(f"[SIM] error: {e}")


    def _open_rsi_chart(self) -> None:
        """Proxy: делегирует открытие RSI Chart контроллеру графиков."""
        self.chart_controller.open_rsi_chart()
        
    def _open_rsi_live_chart(self) -> None:
        """Proxy: делегирует открытие LIVE Chart контроллеру графиков."""
        self.chart_controller.open_rsi_live_chart()

    def _open_candles_live_chart(self) -> None:
        """Proxy: открывает LIVE Candles Chart с выбранным таймфреймом (read-only)."""
        tf_s = 60
        key = ""
        try:
            if hasattr(self, "var_chart_timeframe"):
                key = str(self.var_chart_timeframe.get()).strip()
        except Exception:
            key = ""

        # Tick TF: используем существующий LIVE tick-chart (то же, что Open LIVE Chart)
        if str(key).lower() == "tick":
            self.chart_controller.open_rsi_live_chart()
            return

        try:
            mapping = {
                "1m": 60,
                "5m": 300,
                "15m": 900,
                "1h": 3600,
                "60s": 60,
                "300s": 300,
                "900s": 900,
                "3600s": 3600,
            }
            tf_s = int(mapping.get(key, 60))
        except Exception:
            tf_s = 60

        # Chart-first: switch to embedded Chart tab and run embedded LIVE Candles
        try:
            nb = getattr(self, "nb", None)
            tab_chart = getattr(self, "tab_chart", None)
            if nb is not None and tab_chart is not None:
                nb.select(tab_chart)
        except Exception:
            pass

        self.chart_controller.open_candles_embedded(tf_s)

    def _open_candles_live_chart_popout(self) -> None:
        """Pop-out LIVE Candles window (legacy behavior kept)."""
        tf_s = 60
        key = ""
        try:
            if hasattr(self, "var_chart_timeframe"):
                key = str(self.var_chart_timeframe.get()).strip()
        except Exception:
            key = ""

        if str(key).lower() == "tick":
            self.chart_controller.open_rsi_live_chart()
            return

        try:
            mapping = {
                "1m": 60,
                "5m": 300,
                "15m": 900,
                "1h": 3600,
                "60s": 60,
                "300s": 300,
                "900s": 900,
                "3600s": 3600,
            }
            tf_s = int(mapping.get(key, 60))
        except Exception:
            tf_s = 60

        self.chart_controller.open_candles_live_chart(tf_s)

    def _notify(self, toast_level: str, mb_kind: str, title: str, message: str) -> None:
        """
        Unified UI notifications.
        - toast_level: "info" | "warn" | "error"
        - mb_kind: "info" | "warning" | "error"
        """
        t = getattr(self, "toast", None)
        if t is not None:
            try:
                fn = getattr(t, toast_level, None)
                if callable(fn):
                    fn(message)
                    return
            except Exception:
                pass

        # fallback to messagebox (keep old semantics via mb_kind)
        try:
            if mb_kind == "warning":
                messagebox.showwarning(title, message)
            elif mb_kind == "error":
                messagebox.showerror(title, message)
            else:
                messagebox.showinfo(title, message)
        except Exception:
            pass
  
    def _cmd_open_signals(self) -> None:
        """Open Signals history window (widgets.signals_window)."""
        try:
            from ui.widgets.signals_window import open_signals_window
        except Exception as exc:
            self._notify(
                toast_level="error",
                mb_kind="error",
                title="Signals",
                message=f"Signals window import failed:\n{exc}",
            )
            return

        # UIAPI getter (ленивый, безопасный)
        def _uiapi_getter():
            try:
                return self._ensure_uiapi()
            except Exception:
                return None

        open_signals_window(
            parent=self,
            uiapi_getter=_uiapi_getter,
            limit=500,
        )

    def _cmd_open_via_uiapi(self, method_name: str, fail_prefix: str) -> None:
        api = self._ensure_uiapi()
        if api is None or not hasattr(api, method_name):
            self._notify(
                toast_level="warn",
                mb_kind="warning",
                title="Open",
                message="UIAPI is not available",
            )
            return
        try:
            fn = getattr(api, method_name)
            fn()
        except Exception as e:
            msg = f"{fail_prefix}: {e}"
            self._notify(
                toast_level="warn",
                mb_kind="warning",
                title="Open",
                message=msg,
            )

    def _cmd_open_trades_journal_file(self) -> None:
        self._cmd_open_via_uiapi("open_trades_journal_file", "Failed to open trades journal")

    def _cmd_open_runtime_folder(self) -> None:
        self._cmd_open_via_uiapi("open_runtime_folder", "Failed to open data folder")

    def _cmd_open_trades(self) -> None:
        """Открыть окно с историей сделок.

        При наличии DealsJournal используем новый виджет с router-обновлением
        из снапшота UIAPI/StateEngine. Если импорт не удался — падаем обратно
        на легаси Treeview-представление (без привязки к runtime-именам файлов).
        """
        # --- Новый режим: DealsJournal + snapshot router ---
        if DealsJournal is not None:
            try:
                win = tk.Toplevel(self)
                win.title("Deals journal (SIM/REAL)")
                try:
                    win.configure(bg="#1c1f24")
                except Exception:
                    pass
                win.geometry("980x540")

                journal = DealsJournal(win)
                journal.frame.pack(fill="both", expand=True)

                # Регистрация для _refresh_from_core_snapshot
                try:
                    self.register_deals_journal(journal)
                except Exception:
                    pass

                # При закрытии окна убираем ссылку из router-а
                def _on_close() -> None:
                    try:
                        if getattr(self, "_deals_journal_widget", None) is journal:
                            self._deals_journal_widget = None
                    except Exception:
                        pass
                    try:
                        win.destroy()
                    except Exception:
                        pass

                win.protocol("WM_DELETE_WINDOW", _on_close)

                # 1) Первичная загрузка из снапшота (trades_recent)
                try:
                    api = self._ensure_uiapi()
                    if api is not None and hasattr(api, "get_state_snapshot"):
                        snap = api.get_state_snapshot()
                        if isinstance(snap, dict) and hasattr(journal, "update_from_snapshot"):
                            journal.update_from_snapshot(snap)
                except Exception:
                    # не критично — просто не будет первичной загрузки
                    pass

                # 2) Fallback: подхватываем историю через UIAPI (in-memory recent trades)
                try:
                    api = self._ensure_uiapi()
                    if api is not None and hasattr(api, "get_recent_trades"):
                        rows = api.get_recent_trades() or []
                        if rows and hasattr(journal, "update"):
                            journal.update(rows)
                except Exception:
                    pass

                return
            except Exception as exc:  # noqa: BLE001
                try:
                    self._log(f"[UI] DealsJournal failed, fallback to legacy viewer: {exc!r}")
                except Exception:
                    pass
                # и ниже пойдём по старому пути

        # --- Легаси-режим: простой Treeview на основе последних сделок из UIAPI ---
        try:
            api = self._ensure_uiapi()
            if api is None or not hasattr(api, "get_recent_trades"):
                self._notify(
                    toast_level="warn",
                    mb_kind="info",
                    title="Trades",
                    message="UIAPI is not available.",
                )
                return
            rows = api.get_recent_trades() or []
        except Exception as exc:
            self._notify(
                toast_level="error",
                mb_kind="error",
                title="Trades",
                message=f"Failed to load trades via UIAPI:\n{exc}",
            )
            return

        if not rows:
            self._notify(
                toast_level="info",
                mb_kind="info",
                title="Trades",
                message="No trades to display yet.",
            )
            return

        # Строим окно с Treeview (как раньше)
        win = tk.Toplevel(self)
        win.title("Trades journal (raw)")
        win.geometry("960x520")

        frm = ttk.Frame(win)
        frm.pack(fill="both", expand=True)

        tree = ttk.Treeview(
            frm,
            columns=("ts", "mode", "symbol", "side", "qty", "price", "status", "source"),
            show="headings",
        )
        tree.pack(fill="both", expand=True, side="left")

        vsb = ttk.Scrollbar(frm, orient="vertical", command=tree.yview)
        vsb.pack(side="right", fill="y")
        tree.configure(yscrollcommand=vsb.set)

        headers = {
            "ts": "Time",
            "mode": "Mode",
            "symbol": "Symbol",
            "side": "Side",
            "qty": "Qty",
            "price": "Price",
            "status": "Status",
            "source": "Source / Info",
        }
        widths = {
            "ts": 140,
            "mode": 60,
            "symbol": 80,
            "side": 60,
            "qty": 80,
            "price": 80,
            "status": 80,
            "source": 260,
        }
        for cid in headers:
            tree.heading(cid, text=headers[cid])
            tree.column(cid, width=widths.get(cid, 80), anchor="w")

        def _fmt_float(val, pattern: str = "{:.4f}") -> str:
            try:
                return pattern.format(float(val))
            except Exception:
                return ""

        def _extract_ts(obj: dict) -> str:
            ts = obj.get("ts")
            if ts is None:
                ts = obj.get("transactTime")
                if isinstance(ts, (int, float)):
                    try:
                        return time.strftime(
                            "%Y-%m-%d %H:%M:%S",
                            time.localtime(ts / 1000.0),
                        )
                    except Exception:
                        return str(ts)
                return str(ts or "")
            if isinstance(ts, (int, float)):
                try:
                    return time.strftime(
                        "%Y-%m-%d %H:%M:%S",
                        time.localtime(ts),
                    )
                except Exception:
                    return str(ts)
            return str(ts)

        for obj in rows:
            mode = obj.get("mode") or "?"
            symbol = obj.get("symbol") or "?"
            side = obj.get("side") or "?"
            qty = _fmt_float(obj.get("qty"))
            price = _fmt_float(obj.get("price"))
            status = obj.get("status") or ""
            base_source = obj.get("source") or obj.get("info") or ""

            pnl_pct = obj.get("pnl_pct")
            pnl_cash = obj.get("pnl_cash")
            if pnl_pct is not None or pnl_cash is not None:
                parts = [base_source] if base_source else []
                try:
                    if pnl_pct is not None:
                        parts.append(f"PnL%: {float(pnl_pct):+.2f}%")
                except Exception:
                    pass
                try:
                    if pnl_cash is not None:
                        parts.append(f"PnL: {float(pnl_cash):+.2f}")
                except Exception:
                    pass
                source = " | ".join(parts) if parts else base_source
            else:
                source = base_source

            tree.insert(
                "",
                "end",
                values=(
                    _extract_ts(obj),
                    mode,
                    symbol,
                    side,
                    qty,
                    price,
                    status,
                    source,
                ),
            )

    def _ui_deeplink_open_sim_journal(self, sid: Optional[str] = None) -> None:
        """Deep-link helper used by Strategy Registry to open the Journal view.

        UI-only, read-only. No side-effects.
        """
        try:
            # switch notebook tab first (best-effort)
            try:
                self.nb.select(self.tab_journal)
            except Exception:
                pass

            # stash prefill for the Journal window search box (best-effort)
            try:
                self._sim_journal_prefill = (sid or "").strip()
            except Exception:
                self._sim_journal_prefill = ""

            self._cmd_open_sim_journal()
        except Exception:
            return

    def _ui_focus_strategy_registry(self, sid: str) -> None:
        """Best-effort: switch to Strategies tab and focus a strategy by sid (UI-only)."""
        sid = str(sid or "").strip()
        if not sid:
            return

        # switch to Strategies tab
        try:
            self.nb.select(self.tab_strategies)
        except Exception:
            pass

        # focus if registry hook is available
        try:
            fn = getattr(self, "_strategy_registry_focus_sid", None)
            if callable(fn):
                ok = bool(fn(sid))
                if ok:
                    try:
                        self._strategy_focus_pending_sid = ""
                    except Exception:
                        pass
                    return
        except Exception:
            pass

        # registry not ready or sid not found: stash pending
        try:
            self._strategy_focus_pending_sid = sid
        except Exception:
            pass

    def _calc_strategy_activity(self, window_sec: int = 60) -> dict[str, float]:
        """Return {sid: decisions_per_min} from SIM_DECISION_JOURNAL (UI-only, read-only)."""
        try:
            import json as _json  # local import to avoid global coupling
            now = time.time()
            counts: dict[str, int] = {}

            # Source policy (same spirit as Journal):
            # 1) runtime/events.jsonl
            # 2) fallback: runtime/logs/events.jsonl
            candidates = [
                Path("runtime") / "events.jsonl",
                Path("runtime") / "logs" / "events.jsonl",
            ]

            def _read_lines(p: Path) -> list[str]:
                try:
                    # Use cached tail reader: strategy activity cares only about the recent tail.
                    # Keep this bounded to avoid UI churn on large files.
                    max_lines = 20000
                    return _read_jsonl_tail_lines(p, max_lines)
                except Exception:
                    return []

            lines: list[str] = []
            for p in candidates:
                lines = _read_lines(p)
                if lines:
                    break

            for ln in reversed(lines):
                try:
                    obj = _json.loads(ln)
                except Exception:
                    continue
                if str(obj.get("type") or "") != "SIM_DECISION_JOURNAL":
                    continue

                ts = float(obj.get("ts") or 0.0)
                if window_sec > 0 and (now - ts) > float(window_sec):
                    break

                payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}
                sid = str(payload.get("strategy_sid") or payload.get("sid") or "").strip()
                if not sid:
                    continue

                counts[sid] = counts.get(sid, 0) + 1

            # normalize to decisions/min
            if window_sec <= 0:
                window_sec = 60
            factor = 60.0 / float(window_sec)
            return {sid: round(cnt * factor, 2) for sid, cnt in counts.items()}
        except Exception:
            return {}

    def _cmd_open_sim_journal(self) -> None:
        """Open SIM Decision Journal (events-only, read-only).

        Reads events.jsonl and shows only SIM_DECISION_JOURNAL entries.
        Source policy (UI-only):
          1) runtime/events.jsonl
          2) fallback: runtime/logs/events.jsonl (if no SIM_DECISION_JOURNAL in canonical)
        No side-effects. UI-only.
        """
        try:
            win = tk.Toplevel(self)
            win.title("SIM Decision Journal (read-only)")
            try:
                win.configure(bg="#1c1f24")
            except Exception:
                pass
            win.geometry("1040x720")

            top = ttk.Frame(win, style="Dark.TFrame")
            top.pack(fill="x", padx=8, pady=8)

            var_limit = tk.StringVar(value="2000")
            var_min_conf = tk.StringVar(value="")
            var_search = tk.StringVar(value=getattr(self, "_sim_journal_prefill", "") or "")
            var_auto = tk.BooleanVar(value=False)
            var_show_any = tk.BooleanVar(value=False)

            # strategy name lookup (UI-only, static registry v1)
            _sid_to_name: dict[str, str] = {}
            try:
                from ui.strategy_contract import get_strategy_contracts_v1
                for _s in get_strategy_contracts_v1() or []:
                    sid = str(getattr(_s, "sid", "") or "").strip()
                    name = str(getattr(_s, "name", "") or "").strip()
                    if sid:
                        _sid_to_name[sid] = name or sid
            except Exception:
                _sid_to_name = {}

            ttk.Label(top, text="Tail", style="Muted.TLabel").pack(side="left", padx=(0, 6))
            ent_limit = ttk.Entry(top, textvariable=var_limit, width=8)
            ent_limit.pack(side="left", padx=(0, 12))

            ttk.Label(top, text="Min conf", style="Muted.TLabel").pack(side="left", padx=(0, 6))
            ent_conf = ttk.Entry(top, textvariable=var_min_conf, width=10)
            ent_conf.pack(side="left", padx=(0, 12))

            ttk.Label(top, text="Search", style="Muted.TLabel").pack(side="left", padx=(0, 6))
            ent_search = ttk.Entry(top, textvariable=var_search, width=26)
            ent_search.pack(side="left", padx=(0, 12))

            btn_refresh = ttk.Button(top, text="Refresh", style="Dark.TButton")
            btn_refresh.pack(side="left", padx=(0, 8))

            btn_tail = ttk.Button(top, text="Tail", style="Dark.TButton")
            btn_tail.pack(side="left", padx=(0, 8))

            btn_export = ttk.Button(top, text="Export", style="Dark.TButton")
            btn_export.pack(side="left", padx=(0, 8))

            btn_strategy = ttk.Button(top, text="Open Strategy", style="Dark.TButton")
            btn_strategy.pack(side="left", padx=(0, 12))

            chk_any = ttk.Checkbutton(top, text="All", variable=var_show_any)
            chk_any.pack(side="left", padx=(0, 8))

            chk = ttk.Checkbutton(top, text="Auto", variable=var_auto)
            chk.pack(side="left", padx=(0, 8))

            # UI-only diagnostics: event source + tail-cache stats
            var_src_badge = tk.StringVar(value="events: -")

            # Diagnostics popup button (UI-only)
            btn_diag = ttk.Button(
                top,
                text="ⓘ",
                style="Dark.TButton",
                width=2,
                command=lambda: _open_journal_diagnostics(),
            )
            btn_diag.pack(side="right", padx=(8, 0))

            lbl_src_badge = ttk.Label(top, textvariable=var_src_badge, style="Muted.TLabel")
            lbl_src_badge.pack(side="right", padx=(8, 0))

            body = ttk.Frame(win, style="Dark.TFrame")
            body.pack(fill="both", expand=True, padx=8, pady=(0, 8))

            # table
            cols = ("ts", "sid", "sname", "sym", "conf", "rec", "cid", "hyp")
            tree = ttk.Treeview(body, columns=cols, show="headings", height=16)

            tree.heading("ts", text="ts")
            tree.heading("sid", text="sid")
            tree.heading("sname", text="strategy")
            tree.heading("sym", text="symbol")
            tree.heading("conf", text="conf")
            tree.heading("rec", text="rec")
            tree.heading("cid", text="cid")
            tree.heading("hyp", text="hyp")

            tree.column("ts", width=150, anchor="w")
            tree.column("sid", width=110, anchor="w")
            tree.column("sname", width=130, anchor="w")
            tree.column("sym", width=80, anchor="w")
            tree.column("conf", width=60, anchor="e")
            tree.column("rec", width=100, anchor="w")
            tree.column("cid", width=140, anchor="w")
            tree.column("hyp", width=250, anchor="w")

            vsb = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=vsb.set)
            tree.grid(row=0, column=0, sticky="nsew")
            vsb.grid(row=0, column=1, sticky="ns")
            body.grid_rowconfigure(0, weight=3)
            body.grid_columnconfigure(0, weight=1)

            # details
            details = tk.Text(
                body,
                bg="#0f1116",
                fg="#d6d6d6",
                insertbackground="#d6d6d6",
                height=14,
                wrap="word",
                relief="flat",
                highlightthickness=0,
            )
            details.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
            body.grid_rowconfigure(1, weight=2)

            _entries: list[dict] = []
            _iid_to_index: dict[str, int] = {}
            _journal_source: str = "runtime/events.jsonl"

            def _open_journal_diagnostics():
                """UI-only popup with raw tail-cache diagnostics (no file reads)."""
                try:
                    import json as _json

                    src_path = Path(_journal_source) if _journal_source else (Path("runtime") / "events.jsonl")

                    try:
                        tail_cache_n = int(getattr(win, "_tail_cache_n", 2000) or 2000)
                    except Exception:
                        tail_cache_n = 2000

                    st = _get_jsonl_tail_cache_stats(src_path, max_lines=tail_cache_n) or {}

                    diag = {
                        "source": src_path.as_posix(),
                        "tail_max_lines": tail_cache_n,
                        "cache": {
                            "cached_lines": st.get("cached_lines"),
                            "pos": st.get("pos"),
                            "size": st.get("size"),
                        },
                        "age": {
                            "age_s": st.get("age_s"),
                            "age_state": st.get("age_state"),
                            "age_label": st.get("age_label"),
                        },
                        "last_read": {
                            "last_read_ts": st.get("last_read_ts"),
                            "last_read_label": st.get("last_read_label"),
                        },
                    }

                    w = tk.Toplevel(win)
                    w.title("Journal Diagnostics (read-only)")
                    try:
                        w.configure(bg="#1c1f24")
                    except Exception:
                        pass
                    w.geometry("640x420")

                    top2 = ttk.Frame(w, style="Dark.TFrame")
                    top2.pack(fill="x", padx=8, pady=8)

                    ttk.Label(top2, text="Raw tail-cache diagnostics", style="Muted.TLabel").pack(side="left")

                    btn_close = ttk.Button(top2, text="Close", style="Dark.TButton", command=w.destroy)
                    btn_close.pack(side="right")

                    txt = tk.Text(
                        w,
                        bg="#0f1116",
                        fg="#d6d6d6",
                        insertbackground="#d6d6d6",
                        wrap="none",
                        relief="flat",
                        highlightthickness=0,
                    )
                    txt.pack(fill="both", expand=True, padx=8, pady=(0, 8))

                    txt.insert("1.0", _json.dumps(diag, indent=2, ensure_ascii=False))
                    txt.configure(state="disabled")
                except Exception as e:
                    try:
                        messagebox.showerror("Journal Diagnostics", f"Failed to open:\n{e}")
                    except Exception:
                        pass

            def _parse_line(s: str):
                s = (s or "").strip()
                if not s:
                    return None
                try:
                    import json as _json
                except Exception:
                    _json = None

                if _json is not None:
                    try:
                        obj = _json.loads(s)
                        return obj if isinstance(obj, dict) else None
                    except Exception:
                        pass

                try:
                    import ast as _ast
                except Exception:
                    _ast = None

                if _ast is not None:
                    try:
                        obj = _ast.literal_eval(s)
                        return obj if isinstance(obj, dict) else None
                    except Exception:
                        return None

                return None

            def _extract_ts(e: dict) -> str:
                ts_utc = e.get("ts_utc")
                if isinstance(ts_utc, str) and ts_utc:
                    return ts_utc
                ts = e.get("ts")
                if isinstance(ts, (int, float)):
                    try:
                        return str(float(ts))
                    except Exception:
                        return str(ts)
                if isinstance(ts, str) and ts:
                    return ts
                return ""

            def _get_conf(e: dict):
                payload = e.get("payload") if isinstance(e.get("payload"), dict) else {}
                return payload.get("confidence", None)

            def _get_rec(e: dict) -> str:
                payload = e.get("payload") if isinstance(e.get("payload"), dict) else {}
                return str(payload.get("recommended_action") or "")

            def _get_hyp(e: dict) -> str:
                payload = e.get("payload") if isinstance(e.get("payload"), dict) else {}
                return str(payload.get("hypothesis") or "")

            def _get_sid(e: dict) -> str:
                payload = e.get("payload") if isinstance(e.get("payload"), dict) else {}
                return str(payload.get("strategy_sid") or payload.get("sid") or "")

            def _get_sname(e: dict) -> str:
                sid = _get_sid(e)
                if not sid:
                    return ""
                return str(_sid_to_name.get(sid) or sid)

            def _get_symbol(e: dict) -> str:
                payload = e.get("payload") if isinstance(e.get("payload"), dict) else {}
                sig = payload.get("signals") if isinstance(payload.get("signals"), dict) else {}
                sym = sig.get("symbol") or payload.get("symbol") or ""
                return str(sym or "")

            def _get_cid(e: dict) -> str:
                return str(e.get("correlation_id") or e.get("cid") or "")

            def _passes_filters(e: dict) -> bool:
                # min conf
                raw_min = (var_min_conf.get() or "").strip()
                if raw_min:
                    try:
                        mn = float(raw_min)
                        c = _get_conf(e)
                        if c is None:
                            return False
                        try:
                            if float(c) < mn:
                                return False
                        except Exception:
                            return False
                    except Exception:
                        # invalid min conf -> ignore filter
                        pass

                # search across hyp/rec/cid/signals (stringified)
                q = (var_search.get() or "").strip().lower()
                if q:
                    payload = e.get("payload") if isinstance(e.get("payload"), dict) else {}
                    blob = " ".join(
                        [
                            _get_sid(e),
                            _get_sname(e),
                            _get_symbol(e),
                            _get_hyp(e),
                            _get_rec(e),
                            _get_cid(e),
                            str(payload.get("signals") or ""),
                        ]
                    ).lower()
                    if q not in blob:
                        return False

                return True

            def _render_table() -> None:
                tree.delete(*tree.get_children())
                _iid_to_index.clear()

                shown = 0
                for idx, e in enumerate(_entries):
                    if not _passes_filters(e):
                        continue

                    conf = _get_conf(e)
                    conf_s = ""
                    if conf is not None:
                        try:
                            conf_s = f"{float(conf):.3f}"
                        except Exception:
                            conf_s = str(conf)

                    hyp = _get_hyp(e).replace("\n", " ").strip()
                    if len(hyp) > 120:
                        hyp = hyp[:120] + "…"

                    iid = tree.insert(
                        "",
                        "end",
                        values=(
                            _extract_ts(e),
                            _get_sid(e),
                            _get_sname(e),
                            _get_symbol(e),
                            conf_s,
                            _get_rec(e),
                            _get_cid(e),
                            hyp,
                        ),
                    )
                    _iid_to_index[str(iid)] = idx
                    shown += 1

                details.configure(state="normal")
                details.delete("1.0", "end")
                details.insert("end", f"Source: {_journal_source}\nLoaded: {len(_entries)} | Shown: {shown}\n")
                if len(_entries) == 0:
                    try:
                        if bool(var_show_any.get()):
                            details.insert("end", "Hint: no parsable events in tail (try larger Tail).\n")
                        else:
                            details.insert("end", "Hint: no SIM_DECISION_JOURNAL events in this source. Use Tail or enable All.\n")
                    except Exception:
                        details.insert("end", "Hint: journal is empty. Use Tail for diagnostics.\n")
                details.configure(state="disabled")

            def _format_details(e: dict) -> str:
                payload = e.get("payload") if isinstance(e.get("payload"), dict) else {}
                lines = []
                lines.append(f"type: {e.get('type')}")
                lines.append(f"ts: {_extract_ts(e)}")
                cid = _get_cid(e)
                if cid:
                    lines.append(f"cid: {cid}")

                sid = _get_sid(e)
                if sid:
                    lines.append(f"strategy_sid: {sid}")
                    lines.append(f"strategy_name: {_get_sname(e)}")

                sym = _get_symbol(e)
                if sym:
                    lines.append(f"symbol: {sym}")
                conf = _get_conf(e)
                if conf is not None:
                    lines.append(f"confidence: {conf}")
                rec = _get_rec(e)
                if rec:
                    lines.append(f"recommended_action: {rec}")
                hyp = _get_hyp(e)
                if hyp:
                    lines.append("")
                    lines.append("hypothesis:")
                    lines.append(hyp)

                sig = payload.get("signals") or {}
                if sig:
                    lines.append("")
                    lines.append("signals:")
                    try:
                        import json as _json
                        lines.append(_json.dumps(sig, ensure_ascii=False, indent=2))
                    except Exception:
                        lines.append(str(sig))

                lines.append("")
                lines.append("raw:")
                try:
                    import json as _json
                    lines.append(_json.dumps(e, ensure_ascii=False, indent=2))
                except Exception:
                    lines.append(str(e))

                return "\n".join(lines)

            def _on_select(_evt=None) -> None:
                sel = tree.selection()
                if not sel:
                    return
                iid = str(sel[0])
                if iid not in _iid_to_index:
                    return
                idx = _iid_to_index[iid]
                if idx < 0 or idx >= len(_entries):
                    return
                e = _entries[idx]
                details.configure(state="normal")
                details.delete("1.0", "end")
                details.insert("end", _format_details(e))
                details.configure(state="disabled")

            tree.bind("<<TreeviewSelect>>", _on_select)

            def _load_entries() -> list[dict]:
                nonlocal _journal_source
                try:
                    try:
                        limit = int((var_limit.get() or "2000").strip())
                    except Exception:
                        limit = 2000
                    if limit < 50:
                        limit = 50
                    if limit > 20000:
                        limit = 20000

                    candidates = [
                        Path("runtime") / "events.jsonl",
                        Path("runtime") / "logs" / "events.jsonl",
                    ]

                    def _read_entries(p: Path) -> list[dict]:
                        try:
                            if not p.exists() or not p.is_file():
                                return []
                            # Use cached tail reader. SIM entries can be sparse among other events,
                            # so read a larger bounded tail than the requested limit.
                            try:
                                tail_max = max(8000, int(limit) * 25)
                                if tail_max > 200000:
                                    tail_max = 200000
                            except Exception:
                                tail_max = 8000
                            raw = _read_jsonl_tail_lines(p, tail_max)
                            if not raw:
                                return []
                            out: list[dict] = []
                            want_any = False
                            try:
                                want_any = bool(var_show_any.get())
                            except Exception:
                                want_any = False

                            # Walk from newest to oldest; stop when we have enough.
                            for ln in reversed(raw):
                                obj = _parse_line(ln)
                                if not obj:
                                    continue
                                if (not want_any) and str(obj.get("type") or "") != "SIM_DECISION_JOURNAL":
                                    continue
                                out.append(obj)
                                if len(out) >= limit:
                                    break
                            return out
                        except Exception:
                            return []

                    # 1) canonical
                    primary = candidates[0]
                    out = _read_entries(primary)
                    if out:
                        _journal_source = str(primary)
                        return out

                    # 2) fallback: legacy mirror (only if primary has no SIM entries)
                    secondary = candidates[1]
                    out2 = _read_entries(secondary)
                    if out2:
                        _journal_source = str(secondary)
                        return out2

                    # if nothing found, keep canonical as source for debuggability
                    _journal_source = str(primary)
                    return []
                except Exception:
                    _journal_source = "runtime/events.jsonl"
                    return []

            def _refresh() -> None:
                nonlocal _entries
                _entries = _load_entries()
                _render_table()

                # Update diagnostics badge (read-only)
                try:
                    primary = Path("runtime") / "events.jsonl"
                    secondary = Path("runtime") / "logs" / "events.jsonl"

                    src_path = Path(_journal_source) if _journal_source else primary
                    exists = src_path.exists() and src_path.is_file()

                    # Resolve current Tail and compute the SAME cache key that _load_entries() uses.
                    try:
                        tail_req = int((var_limit.get() or "2000").strip())
                    except Exception:
                        tail_req = 2000
                    if tail_req < 100:
                        tail_req = 100
                    if tail_req > 20000:
                        tail_req = 20000

                    # _load_entries() reads a larger bounded tail because SIM entries can be sparse.
                    try:
                        tail_cache_n = max(8000, int(tail_req) * 25)
                        if tail_cache_n > 200000:
                            tail_cache_n = 200000
                    except Exception:
                        tail_cache_n = 8000

                    # Remember tail cache size used by loader (so the periodic badge tick uses the same cache key)
                    try:
                        win._tail_cache_n = int(tail_cache_n)
                    except Exception:
                        win._tail_cache_n = 2000

                    st = _get_jsonl_tail_cache_stats(src_path, max_lines=tail_cache_n) or {}

                    pos = st.get("pos", 0)
                    size = st.get("size", 0)
                    cached_lines = st.get("cached_lines", 0)

                    age_label = st.get("age_label") or "-"
                    last_read_label = st.get("last_read_label") or "—"

                    # Short prefixes help the badge fit into narrow windows
                    var_src_badge.set(
                        f"ev: {src_path.as_posix()} | SIM={len(_entries)} | c={cached_lines} | p={pos}/{size} | age={age_label} | last_read={last_read_label}"
                    )

                    # remember last full refresh moment (used to throttle auto refresh)
                    win._last_refresh_m = time.monotonic()
                except Exception:
                    pass

            def _do_export() -> None:
                try:
                    if not _entries:
                        messagebox.showinfo("Export", "Nothing to export (journal empty).")
                        return
                    # export only what is currently shown by filters
                    filtered = [e for e in _entries if _passes_filters(e)]
                    if not filtered:
                        messagebox.showinfo("Export", "Nothing to export (filters hide all entries).")
                        return
                    out = export_sim_journal_entries(filtered)
                    messagebox.showinfo("Export", f"Exported:\nCSV: {out.get('csv','')}\nJSON: {out.get('json','')}")
                except Exception as e:
                    messagebox.showerror("Export", f"Export failed:\n{e}")

            def _open_strategy() -> None:
                try:
                    sid = ""
                    try:
                        sel = tree.selection()
                        if sel:
                            vals = tree.item(sel[0], "values") or ()
                            if len(vals) > 1:
                                sid = str(vals[1] or "").strip()  # column "sid"
                    except Exception:
                        sid = ""

                    # fallback: use search only if it matches known sid
                    if not sid:
                        try:
                            cand = str(var_search.get() or "").strip()
                            if cand and cand in _sid_to_name:
                                sid = cand
                        except Exception:
                            sid = ""

                    if not sid:
                        return

                    self._ui_focus_strategy_registry(sid)
                except Exception:
                    return

            def _open_tail_popup() -> None:
                """Open raw tail popup for diagnostics (read-only)."""
                try:
                    src_path = Path(_journal_source) if _journal_source else (Path("runtime") / "events.jsonl")
                    if not src_path.exists() or not src_path.is_file():
                        messagebox.showinfo("Tail", f"events file not found: {src_path.as_posix()}")
                        return

                    win2 = tk.Toplevel(win)
                    win2.title(f"Events Tail (read-only) — {src_path.as_posix()}")
                    try:
                        win2.configure(bg="#1c1f24")
                    except Exception:
                        pass
                    win2.geometry("980x640")

                    top2 = ttk.Frame(win2, style="Dark.TFrame")
                    top2.pack(fill="x", padx=8, pady=8)

                    var_n = tk.StringVar(value="2000")
                    ttk.Label(top2, text="Lines", style="Muted.TLabel").pack(side="left", padx=(0, 6))
                    ent_n = ttk.Entry(top2, textvariable=var_n, width=10)
                    ent_n.pack(side="left", padx=(0, 12))

                    txt = tk.Text(win2, wrap="none", bg="#0f1115", fg="#e6e6e6", insertbackground="#e6e6e6")
                    txt.pack(fill="both", expand=True, padx=8, pady=(0, 8))
                    txt.configure(state="disabled")

                    def _fill() -> None:
                        try:
                            n = int((var_n.get() or "2000").strip())
                        except Exception:
                            n = 2000
                        if n < 100:
                            n = 100
                        if n > 200000:
                            n = 200000

                        raw = _read_jsonl_tail_lines(src_path, n)
                        txt.configure(state="normal")
                        txt.delete("1.0", "end")
                        txt.insert("end", f"Source: {src_path.as_posix()}\nLines: {len(raw)}\n\n")
                        if raw:
                            txt.insert("end", "\n".join(raw))
                        txt.configure(state="disabled")

                    btn_fill = ttk.Button(top2, text="Reload", style="Dark.TButton", command=_fill)
                    btn_fill.pack(side="left", padx=(0, 8))

                    _fill()
                except Exception:
                    return

            btn_refresh.configure(command=_refresh)
            btn_tail.configure(command=_open_tail_popup)
            btn_export.configure(command=_do_export)
            btn_strategy.configure(command=_open_strategy)
            try:
                chk_any.configure(command=_refresh)
            except Exception:
                pass

            # refresh on filter changes
            def _on_filter_change(*_a):
                try:
                    _render_table()
                except Exception:
                    pass

            var_min_conf.trace_add("write", _on_filter_change)
            var_search.trace_add("write", _on_filter_change)

            _refresh()

            def _tick() -> None:
                try:
                    if not win.winfo_exists():
                        return
                except Exception:
                    return

                # Always update badge age (cheap; does NOT read file / redraw table)
                try:
                    src_path = Path(_journal_source) if _journal_source else (Path("runtime") / "events.jsonl")

                    # Use the same tail cache key that loader/refresh used (stored during _refresh()).
                    try:
                        tail_cache_n = int(getattr(win, "_tail_cache_n", 2000) or 2000)
                    except Exception:
                        tail_cache_n = 2000

                    st = _get_jsonl_tail_cache_stats(src_path, max_lines=tail_cache_n) or {}
                    pos = st.get("pos", 0)
                    size = st.get("size", 0)
                    cached_lines = st.get("cached_lines", 0)

                    age_label = st.get("age_label") or "-"
                    last_read_label = st.get("last_read_label") or "—"

                    # Keep SIM count from current loaded table (no reload)
                    var_src_badge.set(
                        f"ev: {src_path.as_posix()} | SIM={len(_entries)} | c={cached_lines} | p={pos}/{size} | age={age_label} | last_read={last_read_label}"
                    )
                except Exception:
                    pass

                # Auto-refresh table at most every ~2s
                try:
                    if bool(var_auto.get()):
                        now_m = time.monotonic()
                        last_m = float(getattr(win, "_last_refresh_m", 0.0) or 0.0)
                        if (now_m - last_m) >= 2.0:
                            _refresh()
                except Exception:
                    pass

                try:
                    win.after(1000, _tick)
                except Exception:
                    pass

            _tick()

        except Exception as e:
            try:
                messagebox.showerror("SIM Decision Journal", f"Failed to open:\n{e}")
            except Exception:
                pass

    def register_deals_journal(self, journal) -> None:
        """Регистрирует DealsJournal widget для router-обновления из снапшота
        и настраивает callback фокуса символа из журнала.
        """
        self._deals_journal_widget = journal
        try:
            if hasattr(journal, "set_focus_callback"):
                journal.set_focus_callback(self._on_journal_focus_symbol)
        except Exception:
            # не даём падать из-за проблем в виджете журнала
            pass

    def _on_journal_focus_symbol(self, symbol: str) -> None:
        """Колбэк из DealsJournal при клике по строке.

        Обновляет выбранный символ в комбобоксе и пишет строку в лог.
        Добавлен лёгкий дебаунс, чтобы не спамить лог при множественных кликах.
        """
        try:
            sym = (symbol or "").strip().upper()
            if not sym:
                return

            now = time.time()
            last_sym = getattr(self, "_last_journal_focus_symbol", None)
            last_ts = getattr(self, "_last_journal_focus_ts", 0.0)

            # если тот же символ приходит чаще, чем раз в 0.3 секунды — игнорируем
            if sym == last_sym and (now - last_ts) < 0.3:
                return

            self._last_journal_focus_symbol = sym
            self._last_journal_focus_ts = now

            # обновляем var_symbol и комбобокс
            try:
                self.var_symbol.set(sym)
            except Exception:
                pass
            combo = getattr(self, "combo", None)
            if combo is not None:
                try:
                    combo.set(sym)
                except Exception:
                    pass

            # диагностическая запись в лог
            try:
                self._log(f"[UI] focus symbol from journal: {sym}")
            except Exception:
                pass
        except Exception:
            # защита от любых сбоев в UI-колбэке
            return

    # -------------------------------------------------------------- actions --
    
    def _ensure_uiapi(self):
        """Lazily construct UIAPI + core state/executor for SIM actions.
        REAL-пути через scripts остаются нетронутыми.
        """
        if getattr(self, "_uiapi", None) is not None:
            return self._uiapi
        try:
            if UIAPI is None:
                self._log("[DIAG] ui_api not available for SIM bridge")
                self._uiapi = None
                return None
        except Exception:
            self._uiapi = None
            return None

        try:
            from core.ui_api import build_ui_bridge  # type: ignore
        except Exception as e:  # noqa: BLE001
            try:
                self._log(f"[DIAG] ui bridge import error: {e!r}")
            except Exception:
                pass
            self._uiapi = None
            return None

        try:
            # IMPORTANT: UI must not construct core primitives (StateEngine/Executor/TPSL) directly.
            # Construction is delegated to core.ui_api.build_ui_bridge().
            self._uiapi = build_ui_bridge(executor_mode="SIM", enable_tpsl=True)
            self._log("[DIAG] ui bridge: UIAPI ready (constructed in core.ui_api)")

            # NEW: передаём текущий режим UI в UIAPI
            try:
                self._uiapi.set_mode(self._mode)
            except Exception:
                pass

            return self._uiapi
        except Exception as e:  # noqa: BLE001
            try:
                self._log(f"[DIAG] ui bridge init failed: {e!r}")
            except Exception:
                pass
            self._uiapi = None
            return None

    def _save_sim_state_via_uiapi(self, snapshot: dict) -> None:
        api = self._ensure_uiapi()
        if api is None:
            return
        try:
            if hasattr(api, "persist_sim_state"):
                api.persist_sim_state(snapshot)
        except Exception:
            pass

    def on_preview(self) -> None:
        """Preview через UIAPI (SIM), REAL не трогаем."""
        api = self._ensure_uiapi()
        if api is None:
            self._notify(
                toast_level="warn",
                mb_kind="warning",
                title="Preview",
                message="UI bridge (UIAPI) недоступен",
            )
            return

        sym = self.var_symbol.get().strip() or DEFAULT_SYMBOLS[0]
        qty_str = self.var_qty.get().strip() or "0"
        try:
            qty = float(qty_str)
        except Exception:
            self._notify(
                toast_level="warn",
                mb_kind="warning",
                title="Preview",
                message="Qty must be a number",
            )
            return

        # 1) пробуем взять last price из ticks_stream.jsonl через _load_chart_prices
        last_price = None
        try:
            _times, prices = self._load_chart_prices(max_points=300)
            if prices:
                last_price = float(prices[-1])
        except Exception:
            last_price = None

        # 2) если тиков ещё нет — берём через UIAPI.get_last_price (если доступно)
        if last_price is None:
            try:
                last_price = api.get_last_price(sym)
            except Exception:
                last_price = None

        pv = api.preview(sym, "BUY", qty, price=last_price)
        if not pv.ok:
            self._notify(
                toast_level="warn",
                mb_kind="info",
                title="Preview",
                message=f"Preview FAILED: {pv.reason}\n{pv.info}",
            )
            return

        raw_price = getattr(pv, "rounded_price", None)
        no_price = raw_price is None

        if no_price:
            msg = (
                "Preview OK\n"
                "Price: n/a (no tick yet)\n"
                f"Qty≈{pv.rounded_qty}"
            )
        else:
            price_disp = str(raw_price)
            msg = (
                "Preview OK\n"
                f"Price≈{price_disp}\n"
                f"Qty≈{pv.rounded_qty}"
            )

        self._notify(
            toast_level="info",
            mb_kind="info",
            title="Preview",
            message=str(msg),
        )
    
    def on_buy_sim(self) -> None:
        """Buy через UIAPI в SIM."""
        api = self._ensure_uiapi()
        if api is None:
            self._notify(
                toast_level="warn",
                mb_kind="warning",
                title=f"Buy ({mode})",
                message="UI bridge (UIAPI) недоступен",
            )
            return

        sym = self.var_symbol.get().strip() or DEFAULT_SYMBOLS[0]
        qty_str = self.var_qty.get().strip() or "0"

        try:
            qty = float(qty_str)
        except Exception:
            self._notify(
                toast_level="warn",
                mb_kind="warning",
                title=f"Buy ({mode})",
                message="Qty must be a number",
            )
            return

        if qty <= 0:
            self._notify(
                toast_level="warn",
                mb_kind="warning",
                title=f"Buy ({mode})",
                message="Quantity must be > 0",
            )
            return

        try:
            mode = str(getattr(self, "_mode", "SIM") or "SIM").upper()
            safe_code = None

            # REAL + file SAFE lock (SAFE_MODE) -> ask unlock code
            if mode == "REAL":
                try:
                    from tools.safe_lock import is_safe_on as _file_safe_on  # type: ignore
                    file_safe = bool(_file_safe_on())
                except Exception:
                    file_safe = False

                if file_safe:
                    safe_code = simpledialog.askstring(
                        "SAFE unlock",
                        "SAFE is ON (file lock: SAFE_MODE).\nEnter unlock code for REAL order:",
                        show="*",
                    )
                    if not safe_code:
                        self._log("[UI] REAL BUY cancelled: no SAFE unlock code")
                        self._notify(
                            toast_level="warn",
                            mb_kind="info",
                            title="Buy (REAL)",
                            message="Cancelled: SAFE unlock code not provided",
                        )
                        return

            # явный лог о том, что это ручной BUY (SIM/REAL) (через UIAPI + StateEngine)
            self._log(f"[UI] manual BUY {mode} {sym} qty={qty} via UIAPI")
            res = api.buy_market(sym, qty, safe_code=safe_code)
            # STEP 2.0 — UI explain-only (no control surface):
            # если BUY заблокирован safety wiring (STOP/PAUSE) — объясняем причину пользователю.
            if res is False:
                try:
                    payload = {}
                    if hasattr(api, "get_trading_status"):
                        payload = api.get_trading_status() or {}
                    if not isinstance(payload, dict):
                        payload = {}
                    state = str(payload.get("state") or "UNKNOWN")
                    mode = "MANUAL_ONLY" if str(payload.get("mode") or "").upper() in ("MANUAL", "MANUAL_ONLY", "") else str(payload.get("mode")).upper()
                    why = payload.get("why_not") or []
                    reason = format_why_not(why)
                    msg = f"BUY blocked by safety policy\nFSM={state} | MODE={mode}"
                    if reason:
                        msg += f"\nReason: {reason}"
                    gate_line = format_gate_line(payload.get("gate"))
                    if gate_line:
                        msg += f"\n{gate_line}"
                    # показать настоящую причину блокировки (PermissionError из ядра)
                    try:
                        if hasattr(api, "get_last_order_error"):
                            err = api.get_last_order_error()
                        else:
                            err = None
                        if err:
                            msg += f"\nError: {err}"
                    except Exception:
                        pass
                    self._notify(
                        toast_level="warn",
                        mb_kind="info",
                        title=f"Buy ({mode})",
                        message=msg,
                    )
                except Exception:
                    # best-effort: UI must not crash on explain path
                    pass
            self._log(f"[UI] ui bridge BUY SIM {sym} qty={qty} -> {res}")

            # FORCE: сразу подтянуть снапшот ядра -> TickUpdater -> EventBus -> UI panels
            self._refresh_from_core_snapshot()
        except Exception as e:  # noqa: BLE001
            self._log(f"[ERROR] ui bridge BUY SIM failed: {e!r}")
            self._notify(
                toast_level="error",
                mb_kind="error",
                title=f"Buy ({mode})",
                message=f"Buy failed: {e}",
            )
    
    def _manual_close_sim_position(self, symbol: str, reason: str = "UI_CLOSE") -> None:
        """Delegate manual close of SIM positions to AutosimController."""
        ctrl = getattr(self, "autosim_controller", None)
        if ctrl is None:
            return

        try:
            ctrl.manual_close_sim_position(symbol=symbol, reason=reason)
        except Exception:
            # не даём autosim-контроллеру ломать UI
            return

    def on_close_sim(self) -> None:
        """Close через UIAPI в SIM."""
        api = self._ensure_uiapi()
        if api is None:
            self._notify(
                toast_level="warn",
                mb_kind="warning",
                title="Close (SIM)",
                message="UI bridge (UIAPI) недоступен",
            )
            return

        sym = self.var_symbol.get().strip() or DEFAULT_SYMBOLS[0]

        # UX: если в SIM нет открытых позиций — не спрашиваем подтверждение, а объясняем.
        try:
            prev = getattr(self, "_sim_log_state", None)
            if prev is not None:
                _eq, _open_cnt = prev
                if int(_open_cnt) <= 0:
                    self._notify(
                        toast_level="info",
                        mb_kind="info",
                        title="Close (SIM)",
                        message="No active SIM positions to close.",
                    )
                    return
        except Exception:
            pass

        if not messagebox.askyesno("Close (SIM)", f"Close SIM position for {sym}?"):
            return

        try:
            # 1) сначала закрываем AUTOSIM и фиксируем PnL
            try:
                self._manual_close_sim_position(sym, reason="UI_CLOSE")
            except Exception:
                pass

            # затем дергаем UIAPI, чтобы TPSL/EXECUTOR тоже знали о закрытии
            api.close_position(sym, reason="UI_close")
            self._log(f"[UI] ui bridge CLOSE SIM {sym}")

            # FORCE: сразу подтянуть снапшот ядра -> TickUpdater -> EventBus -> UI panels
            self._refresh_from_core_snapshot()
        except Exception as e:  # noqa: BLE001
            self._log(f"[ERROR] ui bridge CLOSE SIM failed: {e!r}")
            self._notify(
                toast_level="error",
                mb_kind="error",
                title="Close (SIM)",
                message=f"Close failed: {e}",
            )

    def _run_cli(self, args, tag: str | None = None) -> None:
        # по умолчанию тег зависит от состояния Dry-Run бейджа
        if tag is None:
            try:
                dry_on = bool(getattr(self, "dry_run_ui_on", True))
            except Exception:
                dry_on = True
            tag = "[DRY]" if dry_on else "[REAL]"

        self._log(f"{tag}[RUN] exe={sys.executable} script={' '.join(args)}")
        try:
            out = subprocess.check_output(
                [sys.executable] + args,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if out.strip():
                self._log(f"{tag} " + out.strip())
        except subprocess.CalledProcessError as e:
            self._log(f"{tag}[ERR] " + e.output.strip())
            self._notify(
                toast_level="error",
                mb_kind="error",
                title=tag,
                message=f"{e.output.strip()}",
            )
        except FileNotFoundError as e:
            self._log(f"{tag}[ERR] {repr(e)}")
            self._notify(
                toast_level="error",
                mb_kind="error",
                title=tag,
                message=str(e),
            )

    def on_buy_real(self) -> None:
        # In PRODUCT-MODE, REAL BUY must go through UIAPI (no CLI scripts / no console input).
        # on_buy_sim() already handles preview + safe unlock + api.buy_market(..., safe_code=...)
        self.on_buy_sim()

    def on_close_real(self) -> None:
        if self._safe_is_on():
            self._notify(
                toast_level="warn",
                mb_kind="info",
                title="Close",
                message="SAFE is ON — disable SAFE to place REAL orders",
            )
            return

        sym = self.var_symbol.get().strip()
        default_qty = self.var_qty.get().strip() or "0"
        ans = simpledialog.askstring(
            "Close position",
            f"Enter quantity to close for {sym}\n(Empty = use {default_qty})",
            initialvalue=default_qty,
            parent=self,
        )
        if ans is None:
            return
        q = ans.strip() or default_qty
        try:
            qf = float(q)
        except Exception:
            self._notify(
                toast_level="warn",
                mb_kind="warning",
                title="Close",
                message="Invalid quantity",
            )
            return
        if qf <= 0:
            self._notify(
                toast_level="warn",
                mb_kind="warning",
                title="Close",
                message="Quantity must be > 0",
            )
            return
        if messagebox.askyesno("Confirm", f"Close {qf} {sym} at Market?"):
            self._run_cli(
                [str(SCRIPTS_DIR / "real_sell_market.py"), sym, str(qf), "--ask"]
            )

    def on_panic(self) -> None:
        """Panic через UIAPI в SIM (закрытие позиций) + глобальный PANIC-KILL."""
        api = self._ensure_uiapi()
        if api is None:
            self._notify(
                toast_level="error",
                mb_kind="warning",
                title="Panic",
                message="UI bridge (UIAPI) недоступен",
            )
            return
        sym = self.var_symbol.get().strip() or DEFAULT_SYMBOLS[0]
        if not messagebox.askyesno("Panic", f"Panic close for {sym}?"):
            return

        try:
            # 1) сначала закрываем AUTOSIM и фиксируем PnL
            try:
                self._manual_close_sim_position(sym, reason="UI_PANIC")
            except Exception:
                pass

            # 2) затем уже дергаем UIAPI.panic для закрытия позиции через TPSL
            api.panic(sym)
            self._log(f"[UI] ui bridge PANIC {sym}")

            # FORCE: сразу подтянуть снапшот ядра -> TickUpdater -> EventBus -> UI panels
            self._refresh_from_core_snapshot()

            # 3) и, наконец, включаем глобальный PANIC-KILL:
            #    SAFE_MODE + отключение автолоопа + panic-флаг
            try:
                api.activate_panic_kill(f"UI_PANIC_{sym}")
                self._log("[PANIC] panic_kill activated via UIAPI")
            except Exception as e2:  # noqa: BLE001
                self._log(f"[PANIC][WARN] panic_kill activation failed: {e2!r}")

        except Exception as e:  # noqa: BLE001
            self._log(f"[ERROR] ui bridge PANIC failed: {e!r}")
            self._notify(
                toast_level="error",
                mb_kind="error",
                title="Panic",
                message=f"Panic failed: {e}",
            )

def launch(*args, **kwargs) -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    launch()
