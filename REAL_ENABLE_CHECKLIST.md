
# REAL_ENABLE_CHECKLIST.md

## Before enabling REAL
- [ ] Filled `.env` with `BINANCE_API_KEY` and `BINANCE_SECRET` (keep private).
- [ ] `MONTRIX_MODE=REAL`, `MONTRIX_DRY_RUN=false` only when ready.
- [ ] Fetched `runtime/exchange_info.json` via `python tools/fetch_exchange_info.py`.
- [ ] Verified SIM + TP/SL + Recovery work for hours without crash.
- [ ] Set small test qty meets minQty/minNotional (preview passes).

## First live trade steps
1) `python tools/real_env_check.py` — keys presence check.
2) Start bot with `MONTRIX_MODE=REAL` but keep `MONTRIX_DRY_RUN=true` for one dry session.
3) Flip `MONTRIX_DRY_RUN=false` ONLY after confirming previews are correct and balance is ready.
4) Watch logs; keep Kill-Switch accessible.

## Kill-Switch idea (manual)
- Create an empty file `SAFE_MODE` in project root; on each tick/loop check if it exists — stop sending orders.
- This can be added in 1.0.1; for now, use `MONTRIX_DRY_RUN=true` as a software safety latch.
