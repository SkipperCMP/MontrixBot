
#!/usr/bin/env bash
set -e
mkdir -p runtime
python3 tools/load_env.py >/dev/null 2>&1 || true
if [ ! -f runtime/exchange_info.json ]; then
  echo "[INIT] Fetching exchangeInfo..."
  python3 tools/fetch_exchange_info.py
fi
echo "[RUN] UI (step9)"
python3 scripts/run_ui.py
