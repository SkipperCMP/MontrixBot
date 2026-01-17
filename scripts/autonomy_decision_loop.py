from __future__ import annotations

"""scripts/autonomy_decision_loop.py

Autonomy Decision Loop (v2.2.109)

Canon-safe intent loop:
- REAL: intents-only -> CONFIRM_REQUIRED (exit=2), NEVER auto execute.
- SIM: execute via OrderExecutor and wire TPSL follow (open/close + on_price tick).

Signal source:
- --signal BUY/SELL/HOLD
- --signal AUTO -> uses runtime/signals.jsonl (latest record by symbol)
"""

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]


def _now_ts() -> int:
    try:
        return int(time.time())
    except Exception:
        return 0


def _read_jsonl_tail(path: Path, *, max_lines: int = 2000) -> list[dict]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        tail = lines[-max_lines:] if len(lines) > max_lines else lines
        out: list[dict] = []
        for ln in tail:
            ln = (ln or "").strip()
            if not ln:
                continue
            try:
                obj = json.loads(ln)
                if isinstance(obj, dict):
                    out.append(obj)
            except Exception:
                continue
        return out
    except Exception:
        return []


def _load_latest_signal_record(symbol: str) -> Optional[dict]:
    sym = (symbol or "").upper().strip()
    if not sym:
        return None
    path = ROOT / "runtime" / "signals.jsonl"
    rows = _read_jsonl_tail(path, max_lines=4000)
    for obj in reversed(rows):
        try:
            if str(obj.get("symbol", "")).upper() == sym:
                return obj
        except Exception:
            continue
    return None


def _resolve_signal_side(args_signal: str, symbol: str) -> Tuple[str, Dict[str, Any]]:
    meta: Dict[str, Any] = {}
    s = (args_signal or "AUTO").upper().strip()
    if s and s != "AUTO":
        return s, {"signal_source": "cli"}

    rec = _load_latest_signal_record(symbol)
    if not rec:
        return "HOLD", {"signal_source": "none", "signal_reason": "NO_SIGNAL_RECORD"}

    side = str(rec.get("recommendation_side") or rec.get("side") or "HOLD").upper().strip()
    meta = {
        "signal_source": "runtime/signals.jsonl",
        "signal_ts": rec.get("ts"),
        "signal_side": str(rec.get("side") or ""),
        "recommendation_side": str(rec.get("recommendation_side") or ""),
        "signal_reason": str(rec.get("reason") or ""),
        "recommendation_score": rec.get("recommendation_score"),
        "signal_strength": rec.get("signal_strength"),
    }
    return side or "HOLD", meta


def _resolve_last_price(symbol: str, cli_price: float) -> Optional[float]:
    try:
        if float(cli_price or 0.0) > 0:
            return float(cli_price)
    except Exception:
        pass

    try:
        from core.runtime_state import load_runtime_state

        st = load_runtime_state()
        sim = st.get("sim") if isinstance(st, dict) else None
        if isinstance(sim, dict):
            lp = sim.get("last_price")
            if lp is None:
                return None
            v = float(lp)
            return v if v > 0 else None
    except Exception:
        return None

    return None


def _has_open_position_for_symbol(symbol: str) -> bool:
    """True only if runtime_state has an open position for THIS symbol."""
    try:
        from core.runtime_state import load_runtime_state

        st = load_runtime_state()
        positions = st.get("positions") or {}
        sym = str(symbol or "").upper().strip()
        if not sym:
            return False

        pos = positions.get(sym)
        if pos is None:
            return False

        if isinstance(pos, dict):
            q = pos.get("qty", pos.get("quantity", pos.get("q", 1)))
            try:
                return float(q or 0.0) != 0.0
            except Exception:
                return True

        try:
            return float(pos or 0.0) != 0.0
        except Exception:
            return True
    except Exception:
        return False


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="SIM", choices=["SIM", "REAL"], help="Execution mode")
    ap.add_argument("--signal", default="AUTO", help="BUY/SELL/HOLD or AUTO (from runtime/signals.jsonl)")
    ap.add_argument("--symbol", default="BTCUSDT", help="Symbol")
    ap.add_argument("--qty", type=float, default=0.001, help="Order qty")
    ap.add_argument("--price", type=float, default=0.0, help="Optional last price (for SIM TPSL follow)")
    ap.add_argument("--prefer-noop", action="store_true", default=True)
    ap.add_argument("--no-prefer-noop", action="store_true", default=False)
    args = ap.parse_args(argv)

    mode = str(args.mode or "SIM").upper().strip()
    symbol = str(args.symbol or "BTCUSDT").upper().strip()
    qty = float(args.qty or 0.0)
    prefer_noop = bool(args.prefer_noop) and (not bool(args.no_prefer_noop))

    from core.autonomy_policy import AutonomyPolicyStore
    from core.trading_state_machine import TradingStateMachine
    from core.trade_permission import can_open_new_position_basic
    from core.autonomy_decision import decide_intent

    # Resolve signal
    eff_side, sig_meta = _resolve_signal_side(str(args.signal or "AUTO"), symbol)

    # Permission (SAFE/TECH_STOP/MANUAL_STOP/AUTO_PAUSED)
    policy = AutonomyPolicyStore()
    fsm = TradingStateMachine()
    perm = can_open_new_position_basic(policy, fsm)
    allow_entry = bool(getattr(perm, "allow", False))
    perm_reasons = list(getattr(perm, "reasons", []) or [])

    # Position presence (symbol-scoped)
    has_open = _has_open_position_for_symbol(symbol)

    # Decide intent (canonical signature)
    dr = decide_intent(
        signal_side=str(eff_side),
        has_open_position=bool(has_open),
        allow_entry=bool(allow_entry),
        prefer_noop=prefer_noop,
    )

    out: Dict[str, Any] = {
        "status": str(dr.decision),
        "mode": mode,
        "symbol": symbol,
        "signal": str(eff_side),
        "reasons": list(dr.reasons or []),
        "permission": {"allow_entry": allow_entry, "reasons": perm_reasons},
        "meta": {
            "signal_side": str(eff_side),
            "has_open_position": bool(has_open),
            "allow_entry": bool(allow_entry),
            **sig_meta,
            **(dr.meta or {}),
        },
        "ts": _now_ts(),
    }

    # Observability (best-effort)
    try:
        from core.telemetry_jsonl import ensure_event_telemetry_installed
        from core.event_bus import Event, get_event_bus

        ensure_event_telemetry_installed()
        get_event_bus().publish(
            Event(
                type="autonomy_decision",
                ts=int(time.time()),
                level="INFO",
                topic="autonomy",
                message=f"{out.get('status')} {symbol}",
                meta=out,
            )
        )
    except Exception:
        pass

    # SIM: execute via OrderExecutor + TPSL follow
    if mode == "SIM":
        try:
            from core.state_engine import StateEngine
            from core.executor import OrderExecutor
            from core.tpsl import TPSLManager, TPSSLConfig

            st = StateEngine()
            ex = OrderExecutor(mode="SIM", state=st)
            tpsl = TPSLManager(ex, TPSSLConfig())
            st.attach_tpsl(tpsl)

            last_price = _resolve_last_price(symbol, float(args.price or 0.0))

            if out["status"] == "ENTER":
                r = ex.place_order(symbol=symbol, side="BUY", qty=qty, type_="MARKET", safe_code="AUTO_SIM")
                ep = None
                try:
                    if last_price and float(last_price) > 0:
                        ep = float(last_price)
                    elif r is not None and getattr(r, "price", None) is not None:
                        ep = float(getattr(r, "price"))
                except Exception:
                    ep = None

                if ep is not None and ep > 0:
                    try:
                        tpsl.open_long(symbol, entry_price=float(ep), qty=float(qty))
                        out["meta"]["tpsl_opened"] = True
                        out["meta"]["tpsl_entry_price"] = float(ep)
                    except Exception:
                        out["meta"]["tpsl_opened"] = False

                out["meta"]["sim_exec"] = "BUY+TPSL_OPEN"

            elif out["status"] == "EXIT":
                try:
                    tpsl.close(symbol, reason="signal_exit")
                    out["meta"]["sim_exec"] = "TPSL_CLOSE"
                except Exception:
                    ex.place_order(symbol=symbol, side="SELL", qty=qty, type_="MARKET", safe_code="AUTO_SIM")
                    out["meta"]["sim_exec"] = "SELL_FALLBACK"

            # TPSL follow tick
            if last_price is not None and float(last_price) > 0:
                try:
                    tpsl.on_price(symbol, float(last_price))
                    out["meta"]["tpsl_tick"] = True
                    out["meta"]["tpsl_last_price"] = float(last_price)
                except Exception:
                    out["meta"]["tpsl_tick"] = False

        except Exception as e:
            out["meta"]["sim_exec_error"] = str(e)

        print(json.dumps(out, ensure_ascii=False))
        return 0

    # REAL: intents-only + confirm required (never execute)
    # Unify with Manual Confirm Surface by delegating to OrderExecutor(mode="REAL").
    if out["status"] in ("ENTER", "EXIT"):
        side = "BUY" if out["status"] == "ENTER" else "SELL"

        try:
            from core.executor import OrderExecutor

            ex = OrderExecutor(mode="REAL")
            r = ex.place_order(
                symbol=str(symbol).upper(),
                side=side,
                qty=float(qty),
                type_="MARKET",
                safe_code="AUTO_REAL",
                confirm_actor="autonomy",
            )

            raw = getattr(r, "raw", None) or {}
            if raw.get("status") == "CONFIRM_REQUIRED":
                out.update(
                    {
                        "status": "CONFIRM_REQUIRED",
                        "confirm_token": raw.get("confirm_token"),
                        "confirm_cmd": raw.get("confirm_cmd"),
                        "confirm_actor": raw.get("confirm_actor"),
                        "confirm_expires_ts": raw.get("confirm_expires_ts"),
                        "exit_code": int(raw.get("exit_code") or 2),
                    }
                )
                print(json.dumps(out, ensure_ascii=False))
                return int(out.get("exit_code") or 2)

            # If executor returned something else, remain intents-only and HOLD safely.
            out["status"] = "HOLD"
            out.setdefault("reasons", []).append("REAL_INTENT_NOT_CONFIRMED")
            print(json.dumps(out, ensure_ascii=False))
            return 0

        except Exception as e:
            out["status"] = "HOLD"
            out.setdefault("reasons", []).append("CONFIRM_SERVICE_FAILED")
            out.setdefault("meta", {})["real_intent_error"] = str(e)
            print(json.dumps(out, ensure_ascii=False))
            return 0

    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
