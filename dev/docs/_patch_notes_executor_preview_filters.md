
# core/ui_api.py — patch hint (1.0.1+ step1)

If you call executor.preview_order(symbol, ...), ensure the executor knows the symbol
when using hard_round_and_validate. In this patch we used a placeholder in executor.py.
Two options:

Option A (preferred): modify UIAPI.preview(...) like:
```
pv = self.executor.preview_order(symbol, type_="BUY", qty=qty)
# If hard_round_and_validate is available, it should use `symbol` from args.
```
And inside executor._round_price_qty, remove the placeholder and pass the actual symbol.
This keeps code cohesive.
```python
def _round_price_qty(self, symbol: str, price: float, qty: float):
    if hard_round_and_validate is None:
        ...
    rp, rq, ok_notional, _ = hard_round_and_validate(symbol, price, qty)
    return rp, rq, ok_notional
```
