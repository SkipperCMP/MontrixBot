from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class ClockMeta:
    """
    Minimal clock metadata for observability.

    source:
      - WALL: time.time() based
      - EXCHANGE: WALL + offset_ms (persisted)
    """
    source: str
    offset_ms: int
    recv_window_ms: int
    offset_ts_ms: int  # when offset was written (best-effort)


class SystemClock:
    """
    Core-owned time layer (v1.9.A).

    HARD RULES:
    - No network calls
    - Best-effort file read only
    - No gating / no decisions
    """

    @staticmethod
    def _runtime_dir(root: Optional[Path] = None) -> Path:
        base = root if isinstance(root, Path) else Path(__file__).resolve().parents[1]
        return base / "runtime"

    @staticmethod
    def _offset_file(root: Optional[Path] = None) -> Path:
        return SystemClock._runtime_dir(root) / "time_offset.json"

    @staticmethod
    def _load_offset(root: Optional[Path] = None) -> Tuple[int, int, int]:
        """
        Returns: (offset_ms, recv_window_ms, offset_ts_ms)
        Best-effort. If file missing/invalid -> (0, DEFAULT, 0).
        """
        # Keep same conservative default as tools/binance_time_sync.py
        default_recv_window_ms = 5000

        path = SystemClock._offset_file(root)
        try:
            if not path.exists():
                return 0, default_recv_window_ms, 0
            with path.open("r", encoding="utf-8") as f:
                j = json.load(f) if f else {}
            return (
                int(j.get("offset_ms", 0)),
                int(j.get("recv_window_ms", default_recv_window_ms)),
                int(j.get("ts", 0)),
            )
        except Exception:
            return 0, default_recv_window_ms, 0

    # ----- public API

    @staticmethod
    def now_wall_ms() -> int:
        return int(time.time() * 1000)

    @staticmethod
    def now_wall_ts() -> float:
        return float(time.time())

    @staticmethod
    def now_monotonic_ms() -> int:
        return int(time.monotonic() * 1000)

    @staticmethod
    def now_exchange_ms(*, root: Optional[Path] = None) -> int:
        off_ms, _, _ = SystemClock._load_offset(root)
        return int(SystemClock.now_wall_ms() + int(off_ms))

    @staticmethod
    def recv_window_ms(*, root: Optional[Path] = None) -> int:
        _, rw_ms, _ = SystemClock._load_offset(root)
        return int(rw_ms)

    @staticmethod
    def meta(*, root: Optional[Path] = None) -> ClockMeta:
        off_ms, rw_ms, ts_ms = SystemClock._load_offset(root)
        source = "EXCHANGE" if int(off_ms) != 0 else "WALL"
        return ClockMeta(source=source, offset_ms=int(off_ms), recv_window_ms=int(rw_ms), offset_ts_ms=int(ts_ms))

    @staticmethod
    def meta_dict(*, root: Optional[Path] = None) -> Dict[str, Any]:
        m = SystemClock.meta(root=root)
        return {
            "source": str(m.source),
            "offset_ms": int(m.offset_ms),
            "recv_window_ms": int(m.recv_window_ms),
            "offset_ts_ms": int(m.offset_ts_ms),
        }
