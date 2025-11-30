
@echo off
REM sell.cmd SYMBOL QTY [--no-ask]
setlocal
set ROOT=%~dp0..
cd /d "%ROOT%"
set PY=python
set SCRIPT=%~dp0real_sell_market.py
set ASK=--ask
if "%3"=="--no-ask" set ASK=
"%PY%" "%SCRIPT%" %1 %2 %ASK%
endlocal
