
@echo off
setlocal

if "%1"=="--patch" (
  echo Running patch mode...
)

REM Default entry
python scripts/run_ui.py


endlocal
