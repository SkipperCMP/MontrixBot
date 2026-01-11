from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, DefaultDict, Dict, List, Optional
from collections import defaultdict
import threading
import time
import uuid


def _classify_event(event_type: str, actor: str) -> str:
    """Best-effort event classification for UI/observability (non-normative)."""
    try:
        et = str(event_type or "").upper()
        ac = str(actor or "").lower()
        if ac in ("ui", "human"):
            return "UI"
        if ac in ("sim", "autosim"):
            return "SIM"
        if et.startswith("GATE"):
            return "GATE"
        if et.startswith("FSM") or et.startswith("STATE") or "FSM" in et:
            return "FSM"
        return "SYSTEM"
    except Exception:
        return "SYSTEM"


@dataclass(frozen=True)
class Event:
    """
    Core-owned event envelope.
    - type: short uppercase string (e.g. ORDER, STATE, RISK)
    - ts: unix seconds
    - cid: correlation id for tracing a user action end-to-end
    - actor: who caused it (human/ui/system/strategy/etc.)
    - payload: JSON-serializable dict
    """
    type: str
    ts: float
    cid: str
    actor: str
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": str(self.type),
            "ts": float(self.ts),
            "cid": str(self.cid),
            "correlation_id": str(self.cid),
            "actor": str(self.actor),
            "cls": _classify_event(self.type, self.actor),
            "payload": dict(self.payload or {}),
        }


Callback = Callable[[Event], None]


class EventBus:
    """
    Minimal in-process synchronous pub/sub bus.

    Guarantees:
    - publish() never raises
    - subscriber errors are isolated
    - thread-safe subscribe/unsubscribe/publish
    """
    def __init__(self) -> None:
        self._subs: DefaultDict[str, List[Callback]] = defaultdict(list)
        self._lock = threading.RLock()

    def subscribe(self, event_type: str, cb: Callback) -> None:
        with self._lock:
            lst = self._subs[str(event_type)]
            if cb in lst:
                return
            lst.append(cb)

    def unsubscribe(self, event_type: str, cb: Callback) -> None:
        with self._lock:
            lst = self._subs.get(str(event_type))
            if not lst:
                return
            try:
                lst.remove(cb)
            except ValueError:
                return

    def publish(self, event: Event) -> None:
        try:
            with self._lock:
                callbacks = list(self._subs.get(str(event.type), ())) + list(self._subs.get("*", ()))
            for cb in callbacks:
                try:
                    cb(event)
                except Exception:
                    continue
        except Exception:
            return

    def stats(self) -> Dict[str, int]:
        try:
            with self._lock:
                return {k: len(v) for k, v in self._subs.items()}
        except Exception:
            return {}


# ---- core-owned singleton ----

_BUS: Optional[EventBus] = None
_BUS_LOCK = threading.RLock()


def get_event_bus() -> EventBus:
    global _BUS
    with _BUS_LOCK:
        if _BUS is None:
            _BUS = EventBus()
        return _BUS


def new_cid() -> str:
    return uuid.uuid4().hex


def make_event(event_type: str, payload: Dict[str, Any] | None = None, *, actor: str = "system", cid: str | None = None) -> Event:
    return Event(
        type=str(event_type).upper(),
        ts=float(time.time()),
        cid=str(cid or new_cid()),
        actor=str(actor),
        payload=dict(payload or {}),
    )
