
from __future__ import annotations
import os, json, io
from typing import Tuple, List, Dict, Any

RUNTIME_DIR = "runtime"
STREAM_FILE = os.path.join(RUNTIME_DIR, "deals_stream.jsonl")

def _ensure():
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    if not os.path.exists(STREAM_FILE):
        with open(STREAM_FILE, "w", encoding="utf-8") as f:
            pass

def append_jsonl(row: Dict[str, Any]) -> None:
    _ensure()
    with open(STREAM_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

def read_from(offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
    _ensure()
    rows: List[Dict[str, Any]] = []
    with open(STREAM_FILE, "r", encoding="utf-8") as f:
        f.seek(offset)
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        new_off = f.tell()
    return rows, new_off

def reset_stream() -> None:
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    with open(STREAM_FILE, "w", encoding="utf-8") as f:
        pass
