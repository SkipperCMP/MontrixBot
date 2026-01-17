# LEGACY_MOONBOT_UI.md  
MoonBot UI — Legacy Third-Party UX Reference

Статус: LEGACY / Third-party reference  
Источник: MoonBot (Binance Futures)  
Назначение: UX-референс и анализ анти-паттернов  
Ограничение: не является каноном MontrixBot и не используется напрямую при реализации

---

## 1. Назначение документа

Этот документ фиксирует пользовательский интерфейс MoonBot как **сторонний legacy-пример** торгового UI.

MoonBot используется **исключительно как UX-референс** для:
- плотных таблиц данных,
- фильтрации и сортировки,
- компоновки “список → detail panel”,
- отчётных форм и журналов.

Документ **не задаёт архитектуру** и **не даёт разрешений** на перенос логики управления или исполнения.

---

## 2. Архитектурная модель MoonBot (как есть)

MoonBot реализует классическую action-centric модель:

User → UI → Strategy → Execution

markdown
Копировать код

Характерные свойства:
- UI инициирует BUY / SELL;
- стратегия = исполняющий объект;
- риск и стопы управляются из UI;
- отсутствует Gate-уровень;
- explainability вторична.

⚠️ Эта модель **несовместима** с архитектурой MontrixBot  
(SIM / Gate / REAL, UI read-only).

---

## 3. Market Overview — Таблица рынка

### Что отображается
- торговые пары;
- объёмы (total, short windows);
- spread, funding;
- pump-метрики;
- leverage;
- фильтры и сортировка по условиям.

### UX-ценность
- высокая плотность информации;
- мгновенное сравнение рынков;
- мощная фильтрация.

### Ограничения
В MoonBot таблица используется как **точка входа в сделку**.  
В MontrixBot допустим **только read-only Market / Universe Viewer**  
(без перехода к исполнению).

---

## 4. Settings — Risk / Stops / Conditions

### Что представлено
- Panic Sell настройки;
- Stop Loss / Trailing Stop;
- Take Profit;
- pump / volatility условия;
- blacklist / whitelist;
- тайминги и авто-ограничения.

### UX-ценность
- все ограничения собраны в одном месте;
- удобные чекбоксы и слайдеры;
- ориентировано на опытного трейдера.

### Архитектурные проблемы
- риск = действие;
- стопы управляют исполнением напрямую;
- нет декларативности;
- нет журналируемого decision-flow.

В MontrixBot эти элементы превращаются в:
- **policy и лимиты** (Settings),
- **WHY NOT / Gate reasons** (Explain),
- **события** (Journal).

---

## 5. Strategies — Конфигурация стратегий

### Модель MoonBot
- стратегии активируются напрямую;
- содержат execution-логику;
- управляют входами/выходами;
- параметры меняются “на лету”.

UI позволяет:
- включать / выключать стратегии;
- копировать конфиги;
- изменять параметры без явного аудита.

### Отличие MontrixBot
- стратегия = декларативный контракт;
- SIM анализирует;
- Gate разрешает;
- REAL исполняет;
- UI не управляет.

UX-паттерн “дерево + параметры” допустим  
**без переноса власти**.

---

## 6. Main / Chart — Статус + график + действия

### Что видно
- ценовой график;
- шапка со статусами;
- панель быстрых действий (BUY / Cancel / Panic Sell);
- индикаторы стратегий.

### UX-ценность
- “одно окно, где всё видно”;
- быстрый обзор рынка и состояний.

### Запрещённые элементы
- любые торговые кнопки рядом со статусом;
- Panic Sell;
- прямые действия из UI.

В MontrixBot:
- статус → Main;
- причины → Explain;
- история → Journal / Trade Viewer.

---

## 7. Trades Report — Отчёт по сделкам

### Что отображается
- история сделок;
- PnL, leverage;
- стратегия-источник;
- фильтры по времени;
- экспорт данных;
- detail panel выбранной сделки.

### UX-ценность
- таблица + detail panel;
- удобство пост-анализа;
- экспорт.

### Реализация в MontrixBot
Функциональность распределяется:
- **Journal** — события и решения;
- **Trade Viewer** — одна сделка, таймлайн, контекст SIM/Gate.

---

## 8. Что можно перенести (UX-only)

Разрешено заимствовать:
- плотные таблицы;
- фильтры и сортировки;
- accordion-структуры;
- дерево стратегий;
- detail panel рядом со списком;
- отчётные формы.

Все элементы **без control-surface**.

---

## 9. Что запрещено переносить

Категорически запрещено:
- BUY / SELL / Panic Sell;
- управление ордерами;
- стратегия как action;
- риск как кнопка;
- любые обходы Gate.

См. также: `LEGACY_UI_PATTERNS.md`

---

## 10. Связь с каноном MontrixBot

| MoonBot | MontrixBot |
|-------|------------|
| Market table | Market / Universe Viewer (read-only) |
| Trading screen | Main + Explain |
| Strategy actions | Strategies (inspection) |
| Risk & Stops | Settings + Explain |
| Trades report | Journal + Trade Viewer |

---

## 11) Внешние материалы (справка MoonBot)
Ссылки приведены как справка и не являются частью канона MontrixBot:
https://moon-bot.com/ru/manual/
https://moon-bot.com/ru/manual/settings/
https://moon-bot.com/ru/manual/telegram-connect/
https://moon-bot.com/ru/manual/signals-trading/
https://moon-bot.com/ru/manual/pump-trading/
https://moon-bot.com/ru/manual/stops/
https://moon-bot.com/ru/manual/history/
https://moon-bot.com/ru/manual/pump-detection/
https://moon-bot.com/ru/manual/strategies/

---

## 12. Итог

> **MoonBot оптимизирован под скорость.  
> MontrixBot оптимизирован под контроль и объяснимость.**

MoonBot ценен как UX-референс.  
Архитектура MontrixBot принципиально иная.

Конец документа.