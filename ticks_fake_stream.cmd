
@echo off
setlocal

if "%1"=="--patch" (
  echo Running patch mode...
)

REM Default entry
python tools/ticks_fake_stream.py


endlocal
