from __future__ import annotations
import json, os, threading, tempfile, time
from typing import Any, Dict

class StateManager:
    def __init__(self, path="runtime/state.json"):
        self._path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        if not os.path.exists(self._path):
            self._write_atomic({"positions": {}, "meta": {"created_at": time.time()}})

    def _read(self) -> Dict[str, Any]:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"positions": {}, "meta": {}}

    def _write_atomic(self, data: Dict[str, Any]):
        d = os.path.dirname(self._path)
        fd, tmp = tempfile.mkstemp(prefix="state_", suffix=".json", dir=d)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)
        finally:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass

    def get(self, key: str, default=None):
        with self._lock:
            data = self._read()
            return data.get(key, default)

    def set(self, key: str, value: Any):
        with self._lock:
            data = self._read()
            data[key] = value
            data.setdefault("meta", {})["updated_at"] = time.time()
            self._write_atomic(data)
