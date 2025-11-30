
# scripts/run_ui.py
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
try:
    from ui.app_step8 import launch
except Exception as e:
    raise  # не делаем fallback на step7
# First run without internet uses synthetic feed
launch(symbols=["ADAUSDT","HBARUSDT","BONKUSDT"], use_public_feed=False)
