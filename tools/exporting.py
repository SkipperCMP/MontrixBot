from __future__ import annotations
import os, csv, json, datetime as _dt
from typing import List, Dict, Any, Optional
from tools.formatting import fmt_pnl, fmt_price

EXPORT_DIR_DEFAULT = "exports"

def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def _timestamp() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

def normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "time": row.get("time") or row.get("Time") or row.get("ts") or "",
        "symbol": row.get("symbol") or row.get("Symbol") or "",
        "tier": row.get("tier") or row.get("Tier"),
        "action": row.get("action") or row.get("Action") or "CLOSE",
        "tp": row.get("tp") or row.get("TP"),
        "sl": row.get("sl") or row.get("SL"),
        "pnl_pct": row.get("pnl_pct") or row.get("PnL%") or row.get("pnl_percent"),
        "pnl_abs": row.get("pnl_abs") or row.get("PnL$") or row.get("pnl_abs_usd"),
        "qty": row.get("qty") or row.get("Qty"),
        "entry": row.get("entry") or row.get("Entry") or row.get("entry_price"),
        "exit": row.get("exit") or row.get("Exit") or row.get("exit_price"),
    }

def _format_for_csv(nr: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(nr)
    if out.get("pnl_pct") is not None:
        try:
            out["pnl_pct"] = f"{fmt_pnl(float(out['pnl_pct']))}%"
        except Exception:
            pass
    if out.get("pnl_abs") is not None:
        try:
            out["pnl_abs"] = f"{fmt_price(float(out['pnl_abs']))}"
        except Exception:
            pass
    for k in ("qty", "entry", "exit", "tp", "sl"):
        if out.get(k) is not None:
            try:
                out[k] = fmt_price(float(out[k]))
            except Exception:
                pass
    return out

def export_deals_rows(
    rows: List[Dict[str, Any]],
    out_dir: str = EXPORT_DIR_DEFAULT,
    csv_dir: Optional[str] = None,
    json_dir: Optional[str] = None,
    xlsx_dir: Optional[str] = None,
) -> Dict[str, str]:
    ts = _timestamp()
    if csv_dir or json_dir or xlsx_dir:
        if not csv_dir:
            csv_dir = out_dir
        if not json_dir:
            json_dir = out_dir
        if not xlsx_dir:
            xlsx_dir = out_dir
        _ensure_dir(csv_dir)
        _ensure_dir(json_dir)
        _ensure_dir(xlsx_dir)
        csv_path = os.path.join(csv_dir, f"deals_{ts}.csv")
        json_path = os.path.join(json_dir, f"deals_{ts}.json")
        xlsx_path = os.path.join(xlsx_dir, f"deals_{ts}.xlsx")
    else:
        _ensure_dir(out_dir)
        base = os.path.join(out_dir, f"deals_{ts}")
        csv_path = base + ".csv"
        json_path = base + ".json"
        xlsx_path = base + ".xlsx"

    normalized = [normalize_row(r) for r in rows]
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(normalized, jf, ensure_ascii=False, indent=2)

    formatted = [_format_for_csv(n) for n in normalized]
    fieldnames = ["time", "symbol", "tier", "action", "tp", "sl",
                  "pnl_pct", "pnl_abs", "qty", "entry", "exit"]
    with open(csv_path, "w", encoding="utf-8", newline="") as cf:
        w = csv.DictWriter(cf, fieldnames=fieldnames)
        w.writeheader()
        for r in formatted:
            w.writerow({k: r.get(k, "") for k in fieldnames})

    # optional XLSX export (requires openpyxl)
    xlsx_written = ""
    try:
        import openpyxl  # type: ignore

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Deals"
        ws.append(fieldnames)
        for r in formatted:
            ws.append([r.get(k, "") for k in fieldnames])
        wb.save(xlsx_path)
        xlsx_written = xlsx_path
    except Exception:
        # если openpyxl нет — просто пропускаем XLSX
        xlsx_written = ""

    return {"csv": csv_path, "json": json_path, "xlsx": xlsx_written}


def export_sim_journal_entries(
    entries: List[Dict[str, Any]],
    out_dir: str = EXPORT_DIR_DEFAULT,
    csv_dir: Optional[str] = None,
    json_dir: Optional[str] = None,
) -> Dict[str, str]:
    """
    Export SIM Decision Journal entries (events-only) to CSV + JSON.
    UI-only helper. No side-effects besides writing into exports/.
    """
    _ensure_dir(out_dir)

    base = os.path.join(out_dir, f"sim_journal_{_timestamp()}")
    if csv_dir:
        _ensure_dir(csv_dir)
        csv_path = os.path.join(csv_dir, os.path.basename(base) + ".csv")
    else:
        csv_path = base + ".csv"
    if json_dir:
        _ensure_dir(json_dir)
        json_path = os.path.join(json_dir, os.path.basename(base) + ".json")
    else:
        json_path = base + ".json"

    # normalize
    normalized: List[Dict[str, Any]] = []
    for e in entries:
        payload = e.get("payload") if isinstance(e.get("payload"), dict) else {}
        normalized.append(
            {
                "ts": e.get("ts") or "",
                "ts_utc": e.get("ts_utc") or "",
                "type": e.get("type") or "",
                "correlation_id": e.get("correlation_id") or e.get("cid") or "",
                "confidence": payload.get("confidence", ""),
                "recommended_action": payload.get("recommended_action", ""),
                "hypothesis": payload.get("hypothesis", ""),
                "signals": payload.get("signals", {}),
                "raw": e,
            }
        )

    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(normalized, jf, ensure_ascii=False, indent=2)

    fieldnames = [
        "ts_utc",
        "ts",
        "type",
        "correlation_id",
        "confidence",
        "recommended_action",
        "hypothesis",
        "signals",
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as cf:
        w = csv.DictWriter(cf, fieldnames=fieldnames)
        w.writeheader()
        for r in normalized:
            row = {k: r.get(k, "") for k in fieldnames}
            # keep signals compact in CSV
            if isinstance(row.get("signals"), (dict, list)):
                try:
                    row["signals"] = json.dumps(row["signals"], ensure_ascii=False)
                except Exception:
                    row["signals"] = str(row["signals"])
            w.writerow(row)

    return {"csv": csv_path, "json": json_path}
