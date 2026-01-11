from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Optional, Tuple

from core.runtime_state import load_runtime_state, save_runtime_state


@dataclass(frozen=True)
class PendingConfirm:
    token: str
    cmd: str
    actor: str
    created_ts: int
    expires_ts: int


class RiskyConfirmService:
    """
    RiskyConfirm = two-step intent confirmation.

    Invariants:
    - does NOT allow trading
    - does NOT bypass execution-gates
    - does NOT expand command surface
    - persists into runtime/state.json meta.risky_confirm
    """

    META_KEY = "risky_confirm"

    def request(self, cmd_text: str, actor: str, ttl_s: int = 60) -> PendingConfirm:
        token = uuid.uuid4().hex
        now = int(time.time())
        expires = now + int(ttl_s)

        state = load_runtime_state()
        meta = state.get("meta") or {}
        if not isinstance(meta, dict):
            meta = {}

        meta[self.META_KEY] = {
            "token": token,
            "cmd": str(cmd_text or "").strip(),
            "actor": str(actor or "").strip(),
            "created_ts": now,
            "expires_ts": expires,
        }
        state["meta"] = meta
        save_runtime_state(state)

        return PendingConfirm(
            token=token,
            cmd=str(cmd_text or "").strip(),
            actor=str(actor or "").strip(),
            created_ts=now,
            expires_ts=expires,
        )

    def get_pending(self) -> Optional[PendingConfirm]:
        state = load_runtime_state()
        meta = state.get("meta") or {}
        if not isinstance(meta, dict):
            return None

        raw = meta.get(self.META_KEY)
        if not isinstance(raw, dict):
            return None

        try:
            expires_ts = int(raw.get("expires_ts", 0))
            if int(time.time()) > expires_ts:
                self.clear()
                return None

            return PendingConfirm(
                token=str(raw.get("token", "")),
                cmd=str(raw.get("cmd", "")),
                actor=str(raw.get("actor", "")),
                created_ts=int(raw.get("created_ts", 0)),
                expires_ts=expires_ts,
            )
        except Exception:
            # fail-safe: if corrupted, clear
            self.clear()
            return None

    def clear(self) -> None:
        state = load_runtime_state()
        meta = state.get("meta") or {}
        if not isinstance(meta, dict):
            return
        if self.META_KEY in meta:
            meta.pop(self.META_KEY, None)
            state["meta"] = meta
            save_runtime_state(state)

    def confirm(self, token: str, actor: str) -> Tuple[bool, Optional[str], str]:
        """
        Returns:
          (ok, cmd_text, msg_code)
        msg_code:
          - NO_PENDING_CONFIRM
          - CONFIRM_EXPIRED
          - TOKEN_MISMATCH
          - ACTOR_MISMATCH
          - CONFIRMED
        """
        pending = self.get_pending()
        if not pending:
            return False, None, "NO_PENDING_CONFIRM"

        if str(actor or "").strip() != pending.actor:
            return False, None, "ACTOR_MISMATCH"

        if str(token or "").strip() != pending.token:
            return False, None, "TOKEN_MISMATCH"

        # pending already validated for expiry in get_pending()
        cmd = pending.cmd
        self.clear()
        return True, cmd, "CONFIRMED"
