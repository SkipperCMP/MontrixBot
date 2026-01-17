from pathlib import Path

paths = [
    Path("runtime/events.jsonl"),
    Path("runtime/logs/events.jsonl"),
]

print("=== MontrixBot Journal Diagnostics ===")

for p in paths:
    if p.exists():
        print(f"OK   {p}  size={p.stat().st_size}")
    else:
        print(f"MISS {p}")

print("\n=== Search SIM_DECISION_JOURNAL ===")
for p in paths:
    if not p.exists():
        continue
    found = False
    with p.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "SIM_DECISION_JOURNAL" in line:
                found = True
                break
    print(f"{'FOUND' if found else 'NOHIT'} in {p}")

print("\n=== First 3 lines ===")
for p in paths:
    if not p.exists():
        continue
    print(f"\n--- {p} ---")
    with p.open("r", encoding="utf-8", errors="ignore") as f:
        for i in range(3):
            line = f.readline()
            if not line:
                break
            print(line.rstrip())
