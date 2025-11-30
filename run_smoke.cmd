@echo off
setlocal
cd /d "%~dp0"
echo [SMOKE] Running MontrixBot 1.0_FINAL smoke...
python scripts\smoke_run.py
if %errorlevel% EQU 0 (
  echo [SMOKE] OK
) else (
  echo [SMOKE] FAILED (%errorlevel%)
)
pause
