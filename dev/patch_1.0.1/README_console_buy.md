
# Console Buy Helpers

## Quick usage (PowerShell)
```powershell
.\scripts\buy.ps1 ADAUSDT 9      # спросит SAFE-код
.\scripts\buy.ps1 ADAUSDT 9 --no-ask   # использовать runtime/safe_unlock.key
```

## Quick usage (CMD)
```bat
scripts\buy.cmd ADAUSDT 9
scripts\buy.cmd ADAUSDT 9 --no-ask
```

Оба скрипта вызывают `python scripts/real_buy_market.py <SYMBOL> <QTY> [--ask|--no-ask]` из корня проекта.
