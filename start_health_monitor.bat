
@echo off
REM start_health_monitor.bat — runs health_monitor in a separate window
start "MontrixBot Health" cmd /k python health_monitor.py
