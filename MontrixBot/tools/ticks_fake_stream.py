import json
import time
import random
from pathlib import Path

# корень проекта = два уровня выше этого файла
ROOT_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = ROOT_DIR / "runtime"
RUNTIME_DIR.mkdir(exist_ok=True)

TICKS_FILE = RUNTIME_DIR / "ticks_stream.jsonl"

SYMBOL = "ADAUSDT"   # можешь поменять на любой

def main():
    print(f"[FAKE] writing ticks to {TICKS_FILE}")
    base = 100.0
    price = base

    while True:
        # небольшое случайное движение
        price += random.uniform(-0.3, 0.3)

        obj = {
            "symbol": SYMBOL,
            "price": round(price, 4),
            "bid": round(price - 0.02, 4),
            "ask": round(price + 0.02, 4),
            "ts": int(time.time() * 1000),
        }

        with TICKS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

        print("[FAKE]", obj)
        time.sleep(0.5)  # один тик раз в полсекунды

if __name__ == "__main__":
    main()
