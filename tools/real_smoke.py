
from __future__ import annotations
import sys
from pathlib import Path

def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))

    ok_safe = False
    try:
        from core.orders_real import place_order_real
        try:
            place_order_real("BTCUSDT","BUY",type_="MARKET",quantity=0.0001)
        except PermissionError:
            print("[SAFE] OK: REAL blocked without code")
            ok_safe = True
        except Exception as e:
            print(f"[SAFE] WARN: {type(e).__name__}: {e}")
    except Exception as e:
        print(f"[SAFE] WARN: import failed: {e}")

    ok_time = False
    try:
        from tools import binance_time_sync as ts
        off = abs(int(ts.current_offset().offset_ms))
        if off <= 1000:
            print(f"[TIME] OK: drift {off}ms")
            ok_time = True
        else:
            print(f"[TIME] WARN: drift {off}ms (>1000). Run sync_time()")
    except Exception as e:
        print(f"[TIME] WARN: {e}")

    print("=== SUMMARY ===")
    print(f"SAFE={ok_safe}, TIME={ok_time}")
    sys.exit(0 if (ok_safe and ok_time) else 1)

if __name__ == "__main__":
    main()
