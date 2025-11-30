
# UI интеграция Buy (Market) → REAL

В `ui/app_step8.py` в обработчике кнопки **Buy (Market)** добавьте ветку REAL:

```python
import subprocess, sys, shlex, pathlib

def on_buy_market(self):
    symbol = self.symbol_var.get().strip().upper()
    qty = float(self.qty_var.get())
    root = pathlib.Path(__file__).resolve().parents[1]  # корень проекта
    cmd = f"{sys.executable} scripts/real_buy_market.py {symbol} {qty}"
    try:
        out = subprocess.check_output(shlex.split(cmd), cwd=root)
        self.log(f"[REAL] order: {out.decode('utf-8', 'ignore').strip()}")
    except subprocess.CalledProcessError as e:
        self.log(f"[REAL][ERR] {e.output.decode('utf-8','ignore')}")
    except Exception as e:
        self.log(f"[REAL][ERR] {type(e).__name__}: {e}")
```

Если хочешь, чтобы SAFE-код всегда спрашивался явно (не брался из `runtime/safe_unlock.key`), добавь флаг `--ask` к команде.
