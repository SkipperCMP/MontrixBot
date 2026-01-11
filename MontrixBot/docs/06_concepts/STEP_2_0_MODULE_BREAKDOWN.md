# 🧩 STEP 2.0 — Module Breakdown Specification

**Проект:** MontrixBot  
**Версия:** v2.0-preA (post-GD)  
**Статус:** Breakdown fixed, implementation not started  
**Основание:**  
- SNAPSHOT.md  
- GD_STEP_2_X_AUTO_REAL.md  
- STEP_2_0_ARCHITECTURE.md  
- STEP_2_0_IMPLEMENTATION_BOUNDARY.md  

---

## 1. Purpose

Этот документ:

- фиксирует модульную декомпозицию STEP 2.0,
- определяет ответственность модулей,
- фиксирует зависимости,
- не содержит реализации.

Цель: обеспечить пошаговую реализацию без разрастания STEP 2.0 в монолит.

---

## 2. Global Constraints

- STEP 1.x immutable (read-only).
- SIM does not control REAL.
- UI proxy-only.
- Manual STOP overrides automation.
- Единственная точка контроля открытия сделок: `before_open_position(...)`.
- Любая логика допуска проходит через `CanOpenNewPosition()`.

---

## 3. Module List (STEP 2.0)

Ниже — канонический минимальный набор модулей STEP 2.0.

### 3.1. `AutonomyPolicyStore`

**Responsibility:**
- хранение режима автономии (`MANUAL_ONLY`, `AUTO_ALLOWED`),
- хранение derived state `HARD_STOP` (или отдельный persisted flag),
- выдача текущего режима как source of truth.

**Inputs:**
- команды человека (set_mode, stop, resume).

**Outputs:**
- `mode`,
- `hard_stop_active`.

**Notes:**
- любые изменения режима автономии — только по инициативе человека.

---

### 3.2. `TradingStateMachine` (PauseManager)

**Responsibility:**
- состояние торговли: `TRADING_ACTIVE`, `AUTO_PAUSED`, `HARD_STOPPED`,
- переходы состояния,
- фиксация причин (2–3 причины).

**Inputs:**
- Gate decisions,
- tech blocks,
- команды человека (stop/resume/pause).

**Outputs:**
- `state`,
- `pause_reasons[]`,
- `draining` flag (опционально).

**Notes:**
- auto-resume возможен только из `AUTO_PAUSED`,
- auto-resume запрещён после `HARD_STOPPED`.

---

### 3.3. `GateEngine`

**Responsibility:**
- вычисление `ALLOW | VETO`,
- формирование `reasons[]` и `evidence`.

**Inputs:**
- read-only данные (market status, diagnostics, tech blocks),
- (опционально) SIM evidence как “read-only signals”.

**Outputs:**
- `GateDecision { decision, reasons[], evidence }`.

**Notes:**
- Gate не меняет autonomy mode и не меняет trading state напрямую.

---

### 3.4. `TechnicalBlockRegistry`

**Responsibility:**
- единая точка для “технических блоков” (минимум BNB),
- агрегирование блоков в список причин для veto.

**Inputs:**
- `BNBManager` (и будущие тех-операции).

**Outputs:**
- `tech_blocks[]` (e.g. `BNB_LOW`).

---

### 3.5. `BNBManager`

**Responsibility:**
- контроль доступности BNB для комиссий,
- (если включено) попытка auto-topup,
- выставление техблока `BNB_LOW` при невозможности пополнения.

**Inputs:**
- конфиг enable/disable (только командами),
- баланс/ошибки биржи (read-only).

**Outputs:**
- `BNB_LOW` tech block,
- события `BNB_BLOCK_ON/OFF`.

**Notes:**
- не стратегия,
- не инициирует сделки.

---

### 3.6. `StrategyLockManager`

**Responsibility:**
- enforce правило `1 coin = 1 strategy`,
- выдача и удержание lock до закрытия позиции.

**Inputs:**
- `before_open_position(symbol, strategy_id)`,
- события закрытия позиции (read-only).

**Outputs:**
- `LOCK_OK | LOCK_DENIED` + причина,
- события lock acquired/released.

---

### 3.7. `PermissionOrchestrator`

**Responsibility:**
- реализация единой точки допуска:
  - `CanOpenNewPosition(symbol, strategy_id)`

**Inputs:**
- `AutonomyPolicyStore`,
- `TradingStateMachine`,
- `TechnicalBlockRegistry`,
- `GateEngine`,
- `StrategyLockManager`.

**Outputs:**
- `ALLOW | VETO`,
- `reasons[]`,
- `evidence refs` (через Gate).

**Notes:**
- порядок проверок обязателен (см. Architecture).

---

### 3.8. `CommandRouter` (Proxy-Compatible)

**Responsibility:**
- приём команд от UI/Telegram,
- маршрутизация в правильные модули,
- интеграция с RiskyConfirm.

**Inputs:**
- `/status`,
- `/pause`,
- `/resume`,
- `/stop`,
- `/set_mode`,
- `/bnb_autotopup`,
- risky commands.

**Outputs:**
- изменённые состояния (через stores/managers),
- сообщения пользователю (через NotificationService/UI reply).

**Notes:**
- UI остаётся proxy-only, логика команд живёт здесь/в core.

---

### 3.9. `RiskyConfirmService`

**Responsibility:**
- 2-step confirm,
- контекстная привязка подтверждения к конкретной команде,
- таймаут → abort.

**Inputs:**
- запрос на выполнение risky command.

**Outputs:**
- `ARMED | CONFIRMED | ABORTED`,
- причина отмены.

---

### 3.10. `StatusService`

**Responsibility:**
- генерация краткого `/status`,
- агрегация состояния торговли, режима автономии, причин, позиции, pnl.

**Inputs:**
- `AutonomyPolicyStore`,
- `TradingStateMachine`,
- позиция/PnL (read-only из STEP 1.x),
- tech blocks (read-only).

**Outputs:**
- канонический payload `/status`.

---

### 3.11. `NotificationService`

**Responsibility:**
- Telegram уведомления по триггерам:
  - stop,
  - pause reason changes,
  - resume,
  - tech blocks (BNB).

**Inputs:**
- события из `TradingStateMachine`,
- `BNBManager`,
- (опционально) GateDecision summary.

**Outputs:**
- короткие сообщения (2–3 причины, без кнопок).

---

### 3.12. `DailyReportScheduler`

**Responsibility:**
- запуск суточного отчёта в фиксированное время,
- сбор краткой сводки.

**Inputs:**
- StatusService snapshot,
- агрегаты PnL/событий (read-only).

**Outputs:**
- 1 сообщение в сутки.

---

### 3.13. `AuditEventLog` (PolicyTrace extension, non-control)

**Responsibility:**
- запись событий STEP 2.0 для explainability:
  - GateDecision,
  - state transitions,
  - mode changes,
  - risky confirms,
  - tech blocks,
  - locks.

**Inputs:**
- события от модулей STEP 2.0.

**Outputs:**
- event stream / journal entries.

**Notes:**
- observability only,
- не является gate и не управляет системой.

---

## 4. Dependency Graph (High-Level)

CommandRouter
-> RiskyConfirmService
-> AutonomyPolicyStore
-> TradingStateMachine
-> BNBManager (enable/disable)
-> StatusService

BNBManager -> TechnicalBlockRegistry
GateEngine -> PermissionOrchestrator
StrategyLockManager -> PermissionOrchestrator

AutonomyPolicyStore -> PermissionOrchestrator
TradingStateMachine -> PermissionOrchestrator
TechnicalBlockRegistry -> PermissionOrchestrator

PermissionOrchestrator
-> used by before_open_position(symbol, strategy_id)

TradingStateMachine, GateEngine, BNBManager, StrategyLockManager, RiskyConfirmService
-> AuditEventLog
-> NotificationService

DailyReportScheduler -> StatusService -> NotificationService

yaml
Копировать код

---

## 5. Minimal Implementation Order (Non-Code)

Рекомендуемая последовательность реализации модулей:

1. `AutonomyPolicyStore`
2. `TradingStateMachine`
3. `StatusService`
4. `CommandRouter` (pause/stop/resume/set_mode)
5. `TechnicalBlockRegistry`
6. `BNBManager`
7. `GateEngine` (stub allow/veto with reasons)
8. `StrategyLockManager`
9. `PermissionOrchestrator` + `before_open_position(...)`
10. `NotificationService`
11. `RiskyConfirmService`
12. `DailyReportScheduler`
13. `AuditEventLog` hardening

---

## 6. Boundary Compliance Checklist

Любой модуль STEP 2.0 обязан соблюдать:

- не модифицировать STEP 1.x,
- использовать только allowed integration points,
- не управлять открытыми позициями,
- не инициировать сделки,
- не делать auto-resume после manual stop,
- отдавать причины (2–3) на veto/pause/stop.

---

### ✔ STEP 2.0 Module Breakdown Fixed