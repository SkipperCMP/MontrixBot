# Patch: app_step8 import fix

This patch updates **ui/app_step8.py** with a universal import handler
so the GUI launches correctly in any mode:

- `python ui/app_step8.py`
- `python -m ui.app_step8`
- `run.cmd`
- `run.ps1`
