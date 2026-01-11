
@echo off
setlocal
cd /d "%~dp0"
python scripts\health_dashboard.py
pause
