"""Reports (v2.3.x)

Read-only report generators.

Design:
- Safe to run in any mode; never triggers trading.
- Reads runtime/*.json and runtime/*.jsonl if present.
- Writes output into ./exports/ (or user-provided dir).
"""
