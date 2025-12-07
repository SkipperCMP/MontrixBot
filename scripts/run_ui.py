try:
    from ui.app_step9 import launch
except Exception as e:
    raise  # не делаем fallback на более старый UI
# First run without internet uses synthetic feed
launch(symbols=["ADAUSDT", "HBARUSDT", "BONKUSDT"], use_public_feed=False)
