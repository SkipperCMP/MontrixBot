
from __future__ import annotations
import os, json
from typing import Any, Dict

RUNTIME_DIR = "runtime"
PREFS_FILE = os.path.join(RUNTIME_DIR, "ui_prefs.json")

_DEFAULTS: Dict[str, Any] = {
    "ticker_poll_ms": 250,
    "ticker_max_symbols": 12,
    "ticker_blink": True,
    "ticker_tooltip": True,
}

def ensure_runtime():
    os.makedirs(RUNTIME_DIR, exist_ok=True)

def load_prefs() -> Dict[str, Any]:
    ensure_runtime()
    if not os.path.exists(PREFS_FILE):
        return dict(_DEFAULTS)
    try:
        with open(PREFS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        out = dict(_DEFAULTS)
        for k in _DEFAULTS:
            out[k] = data.get(k, _DEFAULTS[k])
        return out
    except Exception:
        return dict(_DEFAULTS)

def save_prefs(p: Dict[str, Any]) -> None:
    ensure_runtime()
    out = dict(_DEFAULTS)
    out.update(p or {})
    with open(PREFS_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
