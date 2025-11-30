Imports Fix Patch (packages + robust smoke test)
Date: 2025-11-12 20:02:12 UTC

Что внутри:
- core/__init__.py, runtime/__init__.py, telegram/__init__.py, ui/__init__.py, dev/__init__.py
- dev/tpsl_smoke_test.py с шимой sys.path, чтобы запускался командой:
  > python dev\tpsl_smoke_test.py

Как применить (Windows, PowerShell):
1) Распакуйте архив в КОРЕНЬ проекта с заменой файлов.
2) Выполните:
   PS> cd C:\Users\Skipper\Desktop\MontrixBot_1.0.1_READY
   PS> python dev\tpsl_smoke_test.py

Альтернатива:
- Если вы добавите __init__.py, можно запускать как модуль:
   PS> python -m dev.tpsl_smoke_test
