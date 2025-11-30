MontrixBot 1.2-pre1 — STEP2 runtime bootstrap HOTFIX

Содержимое:
- ui/app_step8.py        (исправленный синтаксис и интеграция runtime_bootstrap)
- tools/runtime_bootstrap.py (хелпер ensure_ticks_bootstrap)

Как применить:
1. В каталоге MontrixBot_1.2-pre1_BASELINE_clean распаковать архив с заменой файлов:
   - заменить ui/app_step8.py
   - заменить/добавить tools/runtime_bootstrap.py
2. Запустить: python ui/app_step8.py

Исправления:
- Восстановлена функция _try_import_advisor() (без обрывающегося try).
- Импорт ensure_ticks_bootstrap вынесен из тела _try_import_advisor и
  размещён перед блоком:
      ChartPanel, _CHART_ERR = _try_import_chartpanel()
- Проверен общий синтаксис файла, количество try/except согласовано.

Функция ensure_ticks_bootstrap:
- Должна быть реализована в tools/runtime_bootstrap.py.
- В этом hotfix-файле она либо полная (если применён патч STEP2),
  либо безопасный stub, который просто возвращает 0.
