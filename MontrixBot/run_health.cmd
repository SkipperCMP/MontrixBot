@echo off
setlocal
cd /d "%~dp0"

REM Health Contract runner (snapshot-only, no logs)
REM Exit codes: 0 OK, 2 WARN, 4 FAIL

if "%MTR_HEALTH_INTERVAL%"=="" set MTR_HEALTH_INTERVAL=60

echo [HEALTH] Health Contract loop (interval %MTR_HEALTH_INTERVAL%s)...
:loop
python scripts\health_contract.py
set EC=%ERRORLEVEL%
if "%EC%"=="0" echo [HEALTH] OK
if "%EC%"=="2" echo [HEALTH] WARN
if "%EC%"=="4" echo [HEALTH] FAIL
timeout /t %MTR_HEALTH_INTERVAL% /nobreak >nul
goto loop
