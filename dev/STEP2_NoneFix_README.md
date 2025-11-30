MontrixBot 1.2-pre1 — STEP2 NoneFix (indicators bootstrap)

Содержимое:
- ui/app_step8.py
- tools/runtime_bootstrap.py

Изменения по сравнению с STEP2_hotfix:
1) В ui/app_step8.py добавлен импорт `math`.
2) Функция `_compute_last_indicators`:
   - после расчёта RSI/MACD берёт последние значения;
   - если какое-либо из них равно None, не приводится к float
     или является `math.nan`, функция возвращает (None, None, None);
   - только после проверки возвращает нормальные float значения.
3) За счёт этого:
   - при "разогреве" индикаторов (первые несколько десятков тиков)
     не вызывается simple_rsi_macd_signal с невалидными значениями;
   - устраняется ошибка:
       TypeError("float() argument must be a string or a real number, not 'NoneType'")
     которая логировалась как:
       [DIAG] periodic error: TypeError("float() argument must be...").

Как применить:
- Распаковать архив поверх MontrixBot_1.2-pre1_BASELINE_clean (после STEP2_hotfix),
  согласившись на замену:
    ui/app_step8.py
    tools/runtime_bootstrap.py
- Запустить: python ui/app_step8.py
- Проверить, что:
    * при старте нет спама [DIAG] periodic error;
    * RSI / MACD появляются только после накопления достаточной истории;
    * далее сигналы и авто-SIM работают штатно.
