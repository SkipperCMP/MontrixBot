# MontrixBot
# Workspace cleanup helper (scripts-only)
#
# Goals:
#  - remove Python cache pollution: __pycache__/ and *.pyc
#  - optionally remove runtime log-like artifacts (jsonl/log) WITHOUT touching SSOT/status.json and configs
#
# Safe defaults:
#  - by default cleans only python caches
#  - runtime cleanup requires explicit flag

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]


RUNTIME_KEEP_FILES = {
    # SSOT / configs / policy / fsm
    "status.json",
    "autonomy_policy.json",
    "trading_fsm.json",
    "exchange_info.json",
}


def _iter_pyc(root: Path) -> Iterable[Path]:
    yield from root.rglob("*.pyc")


def _iter_pycache_dirs(root: Path) -> Iterable[Path]:
    for p in root.rglob("__pycache__"):
        if p.is_dir():
            yield p


def _iter_runtime_logs(runtime: Path) -> Iterable[Path]:
    """
    Files that are safe to remove ONLY on explicit request.
    We keep status.json and key config files.
    """
    if not runtime.exists() or not runtime.is_dir():
        return []
    out: list[Path] = []

    # top-level patterns
    for pat in ("*.jsonl", "*.log", "*.csv"):
        out.extend([p for p in runtime.glob(pat) if p.is_file()])

    # nested logs folders (common)
    logs_dir = runtime / "logs"
    if logs_dir.exists() and logs_dir.is_dir():
        for pat in ("*.jsonl", "*.log", "*.csv"):
            out.extend([p for p in logs_dir.rglob(pat) if p.is_file()])

    # filter keep files
    filtered: list[Path] = []
    for p in out:
        if p.name in RUNTIME_KEEP_FILES:
            continue
        # keep any runtime state/config json (conservative)
        if p.suffix.lower() == ".json":
            continue
        filtered.append(p)

    return filtered


def _rm_file(p: Path, dry_run: bool) -> bool:
    try:
        if dry_run:
            return True
        p.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _rm_dir(p: Path, dry_run: bool) -> bool:
    try:
        if dry_run:
            return True
        # remove contents then dir
        for child in sorted(p.rglob("*"), reverse=True):
            try:
                if child.is_file():
                    child.unlink(missing_ok=True)
                elif child.is_dir():
                    child.rmdir()
            except Exception:
                # ignore and continue; we'll report failure at the end if dir still exists
                pass
        try:
            p.rmdir()
        except Exception:
            pass
        return not p.exists()
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="python -m scripts.clean_workspace",
        description="Clean workspace caches (pyc/__pycache__) and optionally runtime logs.",
    )
    ap.add_argument(
        "--runtime-logs",
        action="store_true",
        help="Also remove runtime log-like artifacts (*.jsonl/*.log/*.csv) excluding status.json and configs.",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print what would be removed.",
    )
    args = ap.parse_args()

    dry = bool(args.dry_run)

    print("MontrixBot clean_workspace")
    print(f"ROOT: {ROOT}")
    print(f"dry_run: {dry}")
    print(f"runtime_logs: {bool(args.runtime_logs)}")

    # --- pyc files
    pyc_files = sorted(set(_iter_pyc(ROOT)))
    pyc_ok = 0
    pyc_fail = 0
    for p in pyc_files:
        rel = p.relative_to(ROOT)
        if dry:
            print(f"[DRY] rm file: {rel}")
            pyc_ok += 1
        else:
            ok = _rm_file(p, dry_run=False)
            print(f"{'[OK]' if ok else '[FAIL]'} rm file: {rel}")
            pyc_ok += 1 if ok else 0
            pyc_fail += 0 if ok else 1

    # --- __pycache__ dirs
    pycache_dirs = sorted(set(_iter_pycache_dirs(ROOT)))
    dir_ok = 0
    dir_fail = 0
    for d in pycache_dirs:
        rel = d.relative_to(ROOT)
        if dry:
            print(f"[DRY] rm dir:  {rel}")
            dir_ok += 1
        else:
            ok = _rm_dir(d, dry_run=False)
            print(f"{'[OK]' if ok else '[FAIL]'} rm dir:  {rel}")
            dir_ok += 1 if ok else 0
            dir_fail += 0 if ok else 1

    # --- optional runtime logs
    rt_ok = 0
    rt_fail = 0
    rt_files: list[Path] = []
    if args.runtime_logs:
        runtime = ROOT / "runtime"
        rt_files = sorted(_iter_runtime_logs(runtime))
        for p in rt_files:
            rel = p.relative_to(ROOT)
            if dry:
                print(f"[DRY] rm file: {rel}")
                rt_ok += 1
            else:
                ok = _rm_file(p, dry_run=False)
                print(f"{'[OK]' if ok else '[FAIL]'} rm file: {rel}")
                rt_ok += 1 if ok else 0
                rt_fail += 0 if ok else 1

    print("\nSummary:")
    print(f"  pyc files:     found={len(pyc_files)} ok={pyc_ok} fail={pyc_fail}")
    print(f"  __pycache__:   found={len(pycache_dirs)} ok={dir_ok} fail={dir_fail}")
    if args.runtime_logs:
        print(f"  runtime logs:  found={len(rt_files)} ok={rt_ok} fail={rt_fail}")
    else:
        print("  runtime logs:  skipped (use --runtime-logs)")

    failed = (pyc_fail + dir_fail + rt_fail) > 0
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
