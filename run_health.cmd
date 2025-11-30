
@echo off
setlocal
cd /d "%~dp0"
REM You can change interval via env var below (seconds). 60 = 1 minute.
set MTR_HEALTH_INTERVAL=60
echo [HEALTH] Starting health monitor (interval %MTR_HEALTH_INTERVAL%s)...
python scripts\health_monitor.py
pause
