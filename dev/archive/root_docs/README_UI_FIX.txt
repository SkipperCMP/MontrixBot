UI fix: add missing App._on_symbol_click()

This patch adds a safe fixer script:
- dev/apply_ui_fix_symbol_click.py

How to apply (Windows, PowerShell):
1) Unzip this archive into your project ROOT (same level as ui/, core/, runtime/).
2) Run:
   PS> cd C:\Users\Skipper\Desktop\MontrixBot_1.0.1_READY
   PS> python dev\apply_ui_fix_symbol_click.py

What it does:
- Looks for ui\app.py
- If App._on_symbol_click() is missing, inserts a simple handler method
- Creates a backup file ui\app.py.bak_symbol_click

After that, start your GUI:
   PS> python ui\app.py
