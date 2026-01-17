from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, List

from core.autonomy_policy import AutonomyPolicyStore
from core.trading_state_machine import TradingStateMachine
from core.types_runtime import AutonomyMode


# Event spine (best-effort)
try:
    from core.event_bus import get_event_bus, make_event
except Exception:  # pragma: no cover
    get_event_bus = None  # type: ignore
    make_event = None  # type: ignore


def _emit_cmd(event_type: str, payload: dict) -> None:
    try:
        if get_event_bus is None or make_event is None:
            return
        get_event_bus().publish(make_event(event_type, payload, actor="human"))
    except Exception:
        return

@dataclass(frozen=True)
class CommandResult:
    ok: bool
    message: str


def _norm(s: str) -> str:
    return (s or "").strip()


def _split_cmd(text: str) -> Tuple[str, str]:
    t = _norm(text)
    if not t:
        return "", ""
    parts = t.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    return cmd, arg


def _reasons_from_arg(arg: str, default_reason: str) -> List[str]:
    a = _norm(arg)
    if not a:
        return [default_reason]
    # allow comma-separated or plain text
    if "," in a:
        items = [x.strip() for x in a.split(",") if x.strip()]
        return items[:3] if items else [default_reason]
    return [a][:3]


class CommandRouter:
    """
    Safety Wiring:
      - принимает команды человека
      - меняет только AutonomyPolicyStore и TradingStateMachine
      - без gate, без auto logic, без интеграции в торговлю
    """

    def __init__(self, policy: AutonomyPolicyStore, fsm: TradingStateMachine) -> None:
        self._policy = policy
        self._fsm = fsm

    def handle(self, text: str) -> Optional[CommandResult]:
        cmd, arg = _split_cmd(text)
        if not cmd:
            return None

        # Allowed commands (per COMMAND_SURFACE)
        if cmd in ("/pause", "pause"):
            reasons = _reasons_from_arg(arg, "manual pause")
            self._fsm.manual_pause(reasons=reasons, actor="human")
            _emit_cmd("CMD_PAUSE", {"cmd": "/pause", "reasons": reasons})
            return CommandResult(True, "✅ Пауза включена")

        if cmd in ("/stop", "stop"):
            reasons = _reasons_from_arg(arg, "manual stop")
            self._policy.set_hard_stop(True, actor="human", reason="manual stop")
            self._fsm.manual_stop(reasons=reasons, actor="human")
            _emit_cmd("CMD_STOP", {"cmd": "/stop", "reasons": reasons})
            return CommandResult(True, "⛔ Manual STOP включён (автозапуск запрещён)")

        if cmd in ("/resume", "resume"):
            # снимаем hard stop, но gate-проверку подключим позже строго по FSM_INTEGRATION
            self._policy.set_hard_stop(False, actor="human", reason="manual resume")
            self._fsm.manual_resume_to_active(actor="human")
            _emit_cmd("CMD_RESUME", {"cmd": "/resume"})
            return CommandResult(True, "✅ Resume выполнен")

        if cmd in ("/set_mode", "set_mode"):
            a = arg.upper().strip()
            if a not in ("MANUAL_ONLY", "AUTO_ALLOWED"):
                return CommandResult(
                    False,
                    "❌ Неверный режим. Используй: /set_mode MANUAL_ONLY | /set_mode AUTO_ALLOWED",
                )
            mode = AutonomyMode.MANUAL_ONLY if a == "MANUAL_ONLY" else AutonomyMode.AUTO_ALLOWED
            self._policy.set_mode(mode, actor="human", reason="manual set_mode")
            _emit_cmd("CMD_SET_MODE", {"cmd": "/set_mode", "mode": mode.value})
            return CommandResult(True, f"✅ Режим установлен: {mode.value}")

        # Not our command
        return None
