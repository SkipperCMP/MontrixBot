import json
import os
from core.indicators import rsi, ema
import matplotlib.pyplot as plt

STREAM = os.path.join("runtime", "ticks_stream.jsonl")

def load_stream():
    prices = []
    with open(STREAM, "r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
                prices.append(float(obj["price"]))
            except:
                continue
    return prices

def main():
    if not os.path.exists(STREAM):
        print(f"[ERR] File not found: {STREAM}")
        return
    
    prices = load_stream()
    if len(prices) < 20:
        print("[ERR] Not enough ticks for RSI")
        return

    r = rsi(prices, period=14)
    e = ema(prices, period=20)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10,6), sharex=True)
    fig.suptitle("MontrixBot — RSI from ticks_stream.jsonl")

    ax1.plot(prices, label="Price")
    ax1.plot(e, label="EMA20")
    ax1.set_ylabel("Price")
    ax1.legend()

    ax2.plot(r, label="RSI", color="orange")
    ax2.axhline(70, color='red', linestyle='--')
    ax2.axhline(30, color='blue', linestyle='--')
    ax2.set_ylabel("RSI")
    ax2.set_xlabel("Index")
    ax2.legend()

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
