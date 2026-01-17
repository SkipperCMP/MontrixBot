from __future__ import annotations
from typing import Callable
from runtime.state_manager import StateManager
from core.position_manager import PositionManager
import json, os

from core.panic_facade import activate_panic
from core.autonomy_policy import AutonomyPolicyStore
from core.trading_state_machine import TradingStateMachine
from core.status_service import StatusService
from core.command_router import CommandRouter
from core.risky_confirm import RiskyConfirmService

def install_commands(bot, get_price: Callable[[str], float]):
    state = StateManager()
    pm = PositionManager(state)

    policy = AutonomyPolicyStore()
    fsm = TradingStateMachine()
    status_service = StatusService(policy, fsm)
    cmd_router = CommandRouter(policy, fsm)
    risky_confirm = RiskyConfirmService()

    def cmd_status(update, context):
        payload = status_service.build_status().to_dict()
        # короткий канонический вывод
        lines = []
        lines.append(f"state: {payload['state']}")
        lines.append(f"mode: {payload['mode']}")
        lines.append(f"trading: {'YES' if payload['is_trading'] else 'NO'}")
        if not payload["is_trading"]:
            why = payload.get("why_not") or []
            if why:
                lines.append("why:")
                for r in why[:3]:
                    lines.append(f"- {r}")
        gate = payload.get("gate")
        if isinstance(gate, dict) and gate:
            decision = str(gate.get("decision") or "").upper() or "N/A"
            reasons = gate.get("reasons") or []
            if not isinstance(reasons, list):
                reasons = []
            lines.append(f"gate: {decision}")
            if reasons:
                lines.append("gate_reasons:")
                for r in reasons[:3]:
                    lines.append(f"- {r}")
        pos = payload.get("open_position")
        if pos:
            lines.append("open_position:")
            lines.append(f"- symbol: {pos.get('symbol')}")
            lines.append(f"- side: {pos.get('side')}")
            lines.append(f"- entry: {pos.get('entry')}")
            lines.append(f"- current: {pos.get('current')}")
            lines.append(f"- pnl: {pos.get('pnl')}")
        update.message.reply_text("\n".join(lines))

    def _is_enabled():
        # включать только когда будет готов RiskyConfirm (по канону)
        return os.environ.get("MONTRIX_ENABLE_RISKY_CMDS", "0") == "1"

    def _extract_confirm_token(args):
        """
        Accepts tokens only as: confirm=<token>
        Returns: (token_or_none, args_without_confirm:list[str])
        """
        token = None
        out = []
        for a in (args or []):
            s = str(a)
            if s.startswith("confirm=") and token is None:
                token = s.split("=", 1)[1].strip()
                continue
            out.append(s)
        return token, out

    def _risky_two_step(update, base_cmd: str, args_list):
        """
        Two-step protocol WITHOUT new commands:
          1) /pause           -> returns 'repeat with confirm=TOKEN'
          2) /pause confirm=TOKEN -> executes pending cmd (must match base_cmd)
        """
        token, cleaned_args = _extract_confirm_token(args_list)
        arg_text = " ".join(cleaned_args).strip()
        normalized_cmd = (base_cmd + (" " + arg_text if arg_text else "")).strip()

        if token:
            ok, cmd_text, msg = risky_confirm.confirm(token, actor="telegram")
            if not ok:
                update.message.reply_text(f"❌ Confirmation failed: {msg}")
                return None

            # strict match: must confirm the same command family (no cross-confirm)
            if not (cmd_text or "").strip().lower().startswith(base_cmd.strip().lower()):
                update.message.reply_text("❌ Confirmation token is not for this command")
                return None

            res = cmd_router.handle(cmd_text)
            update.message.reply_text(res.message if res else "No-op")
            return res

        # no token => request confirmation
        pending = risky_confirm.request(normalized_cmd, actor="telegram", ttl_s=60)
        update.message.reply_text(
            "⚠️ Confirmation required.\n"
            f"Repeat the SAME command with:\n"
            f"{base_cmd} confirm={pending.token}"
        )
        return None

    def cmd_pause(update, context):
        if not _is_enabled():
            update.message.reply_text("Risky commands disabled (enable MONTRIX_ENABLE_RISKY_CMDS=1).")
            return
        _risky_two_step(update, "/pause", context.args or [])

    def cmd_stop(update, context):
        if not _is_enabled():
            update.message.reply_text("Risky commands disabled (enable MONTRIX_ENABLE_RISKY_CMDS=1).")
            return
        _risky_two_step(update, "/stop", context.args or [])

    def cmd_resume(update, context):
        if not _is_enabled():
            update.message.reply_text("Risky commands disabled (enable MONTRIX_ENABLE_RISKY_CMDS=1).")
            return
        _risky_two_step(update, "/resume", context.args or [])

    def cmd_set_mode(update, context):
        if not _is_enabled():
            update.message.reply_text("Risky commands disabled (enable MONTRIX_ENABLE_RISKY_CMDS=1).")
            return
        _risky_two_step(update, "/set_mode", context.args or [])

    def cmd_autoloop(update, context):
        args = context.args or []
        if not args:
            update.message.reply_text("Usage: /autoloop on|off")
            return
        on = args[0].lower() == "on"
        os.makedirs("runtime", exist_ok=True)
        try:
            with open("runtime/settings.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
        cfg.setdefault("tpsl_autoloop", {})["enabled"] = on
        with open("runtime/settings.json", "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        update.message.reply_text(f"TPSL-autoloop: {'ON' if on else 'OFF'}")

    def cmd_update_tp(update, context):
        try:
            sym = str(context.args[0]).upper()
            tp = float(context.args[1])
        except Exception:
            update.message.reply_text("Usage: /update_tp SYMBOL PRICE")
            return
        pm.set_tp(sym, tp)
        update.message.reply_text(f"{sym}: TP -> {tp:.6f}")

    def cmd_update_sl(update, context):
        try:
            sym = str(context.args[0]).upper()
            sl = float(context.args[1])
        except Exception:
            update.message.reply_text("Usage: /update_sl SYMBOL PRICE")
            return
        pm.set_sl(sym, sl)
        update.message.reply_text(f"{sym}: SL -> {sl:.6f}")

    def cmd_tpsl(update, context):
        pos = pm.get_open_positions()
        if not pos:
            update.message.reply_text("No open positions.")
            return
        lines = []
        for s, p in pos.items():
            lines.append(f"{s}: qty={p.qty}, entry={p.entry_price:.6f}, tp={p.tp}, sl={p.sl}")
        update.message.reply_text("\n".join(lines))

    def cmd_panic(update, context):
        """
        Глобальный PANIC-KILL из Telegram.

        Семантика:
        - инициирует глобальный PANIC через core.panic_facade;
        - PANIC является аварийным сигналом для runtime и смежных компонентов;
        - не гарантирует включение SAFE_MODE, остановку TPSL или файловые эффекты
          напрямую (это зона ответственности runtime-уровня).

        Важно:
        - команда best-effort и не должна падать;
        - поведение PANIC определяется реализацией runtime.panic_tools.
        """
        reason = "TG_PANIC"
        try:
            args = context.args or []
            if args:
                reason = "TG_PANIC: " + " ".join(str(a) for a in args)
        except Exception:
            reason = "TG_PANIC"

        try:
            activate_panic(reason)
            update.message.reply_text(
                "PANIC-KILL activated. Runtime emergency signal sent."
            )
        except Exception as e:
            update.message.reply_text(f"PANIC-KILL failed: {e!r}")

    try:
        bot.add_command("autoloop", cmd_autoloop)
        bot.add_command("update_tp", cmd_update_tp)
        bot.add_command("update_sl", cmd_update_sl)
        bot.add_command("tpsl", cmd_tpsl)
        bot.add_command("panic", cmd_panic)
        bot.add_command("status", cmd_status)

        # risky — отключены по умолчанию до RiskyConfirm wiring
        bot.add_command("pause", cmd_pause)
        bot.add_command("stop", cmd_stop)
        bot.add_command("resume", cmd_resume)
        bot.add_command("set_mode", cmd_set_mode)

    except Exception:
        pass

