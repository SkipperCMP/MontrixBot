# ui/app_step7.py — compatibility shim
# If scripts/run_ui.py falls back to app_step7, forward to app_step8.
def launch(*args, **kwargs):
    from .app_step8 import launch as _launch
    return _launch(*args, **kwargs)
