# MontrixBot
# Unified audit & contract runner (scripts-only)
#
# Runs:
#  - Contracts: check_status_contract, check_ui_reason_string, check_explain_trace_contract
#  - Extra local tests: compileall, debug_runtime_sanity, test_runtime_state, test_state_manager, test_history_retention
#  - Post-test cleanup: scripts.clean_workspace (pyc/__pycache__, optional runtime logs) unless --no-clean
#  - Static audits: secrets/.env, runtime & pyc pollution, risky commands in scripts, entry-point checks
#
# Exit code:
#  - 0 if all mandatory contracts pass and no CRITICAL findings
#  - 1 otherwise
#
# v2.2.69:
#  - audit_all now self-cleans __pycache__/pyc after tests (optional), so the pollution
#    audit reflects the final workspace state (no more "pyc pollution" false positives).
#  - Added flags: --no-clean, --clean-runtime-logs, --no-compileall.
#  - v2.2.71: Added flags: --allow-env, --allow-runtime-artifacts (audit profile noise control).

from __future__ import annotations

import argparse
import os
import re
import sys

sys.dont_write_bytecode = True
import subprocess
from pathlib import Path
from typing import List, Tuple


ROOT = Path(__file__).resolve().parents[1]


DANGEROUS_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("rm -rf", re.compile(r"\brm\s+-rf\b", re.IGNORECASE)),
    ("del /s", re.compile(r"\bdel\s+/s\b", re.IGNORECASE)),
    ("rmdir /s", re.compile(r"\brmdir\s+/s\b", re.IGNORECASE)),
    ("Remove-Item -Recurse", re.compile(r"\bRemove-Item\b.*\b-Recurse\b", re.IGNORECASE)),
    ("curl", re.compile(r"\bcurl\b", re.IGNORECASE)),
    ("wget", re.compile(r"\bwget\b", re.IGNORECASE)),
    ("Invoke-WebRequest", re.compile(r"\bInvoke-WebRequest\b", re.IGNORECASE)),
    ("Invoke-RestMethod", re.compile(r"\bInvoke-RestMethod\b", re.IGNORECASE)),
]


def _hr(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def _run(cmd: List[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> Tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return p.returncode, p.stdout


def _run_module(module: str, *, args: List[str] | None = None, env: dict[str, str] | None = None) -> Tuple[int, str]:
    cmd = [sys.executable, "-m", module]
    if args:
        cmd.extend(args)
    return _run(cmd, cwd=ROOT, env=env)


def _read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        try:
            return path.read_text(errors="replace")
        except Exception:
            return ""


def _audit_secrets(findings: List[str], *, allow_env: bool) -> None:
    env_path = ROOT / ".env"
    if env_path.exists():
        txt = _read_text_safe(env_path)
        if re.search(r"\bBINANCE_(API_KEY|SECRET)\s*=", txt):
            if allow_env:
                findings.append("WARN: .env contains BINANCE_API_KEY / BINANCE_SECRET (allowed by --allow-env).")
            else:
                findings.append("CRITICAL: .env contains BINANCE_API_KEY / BINANCE_SECRET (rotate keys; remove from releases).")
        else:
            findings.append("WARN: .env exists in repo (should not be in release archives).")


def _audit_pollution(findings: List[str], *, allow_runtime_artifacts: bool) -> None:
    pyc = list(ROOT.rglob("*.pyc"))
    if pyc:
        findings.append(f"WARN: found {len(pyc)} '*.pyc' files (release pollution).")

    pycache = [p for p in ROOT.rglob("__pycache__") if p.is_dir()]
    if pycache:
        findings.append(f"WARN: found {len(pycache)} '__pycache__' directories (release pollution).")

    runtime = ROOT / "runtime"
    if runtime.exists() and runtime.is_dir():
        big = []
        for p in runtime.rglob("*"):
            if p.is_file():
                sz = p.stat().st_size
                if sz >= 200_000:
                    big.append((p, sz))
        if big:
            details = ", ".join([f"{p.relative_to(ROOT)}({sz}B)" for p, sz in big])
            if allow_runtime_artifacts:
                findings.append(
                    "INFO: runtime/ contains large artifacts (allowed by --allow-runtime-artifacts): " + details
                )
            else:
                findings.append(
                    "WARN: runtime/ contains large artifacts: " + details
                )


def _audit_scripts_commands(findings: List[str]) -> None:
    exts = {".sh", ".cmd", ".ps1", ".bat", ".txt"}
    candidates = []
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts:
            candidates.append(p)

    hits = []
    for p in candidates:
        txt = _read_text_safe(p)
        for name, pat in DANGEROUS_PATTERNS:
            if pat.search(txt):
                hits.append((name, p))
    if hits:
        uniq = []
        seen = set()
        for name, p in hits:
            k = (name, str(p))
            if k not in seen:
                seen.add(k)
                uniq.append((name, p))
        findings.append(
            "WARN: potentially risky commands detected: "
            + "; ".join([f"{name} in {p.relative_to(ROOT)}" for name, p in uniq])
        )


def _audit_entry_points(findings: List[str]) -> None:
    run_cmd = ROOT / "run.cmd"
    run_sh = ROOT / "run.sh"
    if run_cmd.exists():
        txt = _read_text_safe(run_cmd)
        if "ui.main_app" not in txt and "scripts/run_ui.py" not in txt:
            findings.append("WARN: run.cmd does not reference ui.main_app or scripts/run_ui.py (unexpected UI entry point).")

    if run_sh.exists():
        txt = _read_text_safe(run_sh)
        if "scripts/run_ui.py" not in txt and "ui.main_app" not in txt:
            findings.append("WARN: run.sh does not reference scripts/run_ui.py or ui.main_app (unexpected UI entry point).")
        if "step9" in txt.lower():
            findings.append("INFO: run.sh contains 'step9' wording (cosmetic legacy).")



def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.audit_all",
        description="MontrixBot — Unified Audit Runner",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not auto-remove __pycache__/pyc after tests (static audits may report pollution).",
    )
    parser.add_argument(
        "--clean-runtime-logs",
        action="store_true",
        help="Also remove runtime *.log and runtime/logs via scripts.clean_workspace --runtime-logs.",
    )
    parser.add_argument(
        "--no-compileall",
        action="store_true",
        help="Skip compileall (faster; also avoids generating pyc that then need cleanup).",
    )

    # Audit profile flags (reduce known/accepted noise in static audits)
    parser.add_argument(
        "--allow-env",
        action="store_true",
        help="Allow .env with BINANCE_API_KEY/BINANCE_SECRET (downgrade CRITICAL to WARN).",
    )
    parser.add_argument(
        "--allow-runtime-artifacts",
        action="store_true",
        help="Allow large runtime artifacts (downgrade WARN to INFO).",
    )

    args = parser.parse_args()

    findings: List[str] = []
    failures: List[str] = []

    child_env = os.environ.copy()
    # Reduce bytecode artifacts from subprocesses (compileall may still generate them).
    child_env.setdefault("PYTHONDONTWRITEBYTECODE", "1")

    _hr("MontrixBot — Unified Audit Runner")
    ver_file = ROOT / "VERSION"
    if ver_file.exists():
        print("VERSION:", _read_text_safe(ver_file).strip())
    print("PY:", sys.version.split()[0])
    print("ROOT:", ROOT)

    # Contracts (mandatory)
    _hr("Contracts")
    for mod in ["scripts.check_status_contract", "scripts.check_ui_reason_string", "scripts.check_explain_trace_contract"]:
        code, out = _run_module(mod, env=child_env)
        print(f"--- {mod} (exit={code}) ---")
        print(out.rstrip())
        if code != 0:
            failures.append(mod)

    # Extra tests (reported)
    _hr("Extra tests")
    if not args.no_compileall:
        code, out = _run([sys.executable, "-m", "compileall", "-q", "."], cwd=ROOT, env=child_env)
        print(f"--- compileall (exit={code}) ---")
        if out.strip():
            print(out.rstrip())
        if code != 0:
            failures.append("compileall")
    else:
        print("--- compileall (skipped by --no-compileall) ---")

    for mod in [
        "scripts.debug_runtime_sanity",
        "scripts.test_ui_no_runtime_writes",
        "scripts.test_headless_contract",
        "scripts.test_runtime_state",
        "scripts.test_state_manager",
        "scripts.test_history_retention",
    ]:

        code, out = _run_module(mod, env=child_env)
        print(f"--- {mod} (exit={code}) ---")
        print(out.rstrip())
        if code != 0:
            failures.append(mod)

    # Post-test cleanup (so static audits reflect the final workspace state)
    if not args.no_clean:
        clean_args: List[str] = []
        if args.clean_runtime_logs:
            clean_args.append("--runtime-logs")
        code, out = _run_module("scripts.clean_workspace", args=clean_args, env=child_env)
        print(f"--- scripts.clean_workspace (exit={code}) ---")
        if out.strip():
            print(out.rstrip())
        if code != 0:
            failures.append("scripts.clean_workspace")
    else:
        print("--- scripts.clean_workspace (skipped by --no-clean) ---")

    # Static audits
    _hr("Static audits")
    _audit_secrets(findings, allow_env=args.allow_env)
    _audit_pollution(findings, allow_runtime_artifacts=args.allow_runtime_artifacts)
    _audit_scripts_commands(findings)
    _audit_entry_points(findings)

    if not findings:
        print("No findings.")
    else:
        for f in findings:
            print("-", f)

    _hr("Summary")

    profile = "strict"
    if args.allow_env or args.allow_runtime_artifacts:
        flags = []
        if args.allow_env:
            flags.append("allow-env")
        if args.allow_runtime_artifacts:
            flags.append("allow-runtime-artifacts")
        profile = "relaxed (" + ", ".join(flags) + ")"

    print(f"Audit profile: {profile}")

    if failures:
        print("FAIL modules/tests:", ", ".join(failures))
    else:
        print("All tests/modules passed.")

    critical = any(f.startswith("CRITICAL:") for f in findings)
    if failures or critical:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
