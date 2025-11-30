from __future__ import annotations
from typing import Callable
from runtime.state_manager import StateManager
from core.position_manager import PositionManager
import json, os

def install_commands(bot, get_price: Callable[[str], float]):
    state = StateManager()
    pm = PositionManager(state)

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

    try:
        bot.add_command("autoloop", cmd_autoloop)
        bot.add_command("update_tp", cmd_update_tp)
        bot.add_command("update_sl", cmd_update_sl)
        bot.add_command("tpsl", cmd_tpsl)
    except Exception:
        pass
