# ✅ STEP 2.0 — Pre-Implementation Compliance Checklist (Dry Audit)

**Проект:** MontrixBot  
**Версия:** v2.0-preA (post-GD)  
**Статус:** Checklist fixed, implementation not started  
**Основание:**  
- SNAPSHOT.md  
- GD_STEP_2_X_AUTO_REAL.md  
- STEP_2_0_ARCHITECTURE.md  
- STEP_2_0_IMPLEMENTATION_BOUNDARY.md  
- STEP_2_0_MODULE_BREAKDOWN.md  
- STEP_2_0_FSM_INTEGRATION.md  
- STEP_2_0_COMMAND_SURFACE.md  
- STEP_2_0_GATE_EVIDENCE_CONTRACT.md  

---

## 1. Purpose

Этот документ:

- фиксирует сухой checklist-аудит готовности к реализации STEP 2.0,
- позволяет дать ответ **GO / NO-GO** без обсуждений,
- не содержит реализации и не расширяет boundary.

---

## 2. Audit Results Vocabulary

- `PASS`   — условие выполняется и проверено
- `FAIL`   — условие нарушено
- `VERIFY` — не видно нарушений, но требуется локальная проверка в репо/коде/процессе

---

## 3. Canon Compliance

### A) Governance & Snapshot

- [PASS] STEP 2.x разрешён только через `GD_STEP_2_X_AUTO_REAL.md`; STEP 1.x immutable.
- [PASS] SNAPSHOT актуален и используется как фиксатор состояния.
- [PASS] Архитектурные якоря STEP 2.0 добавлены:
  - Architecture
  - Implementation Boundary
  - Module Breakdown
  - FSM Integration
  - Command Surface
  - Gate Evidence Contract

---

## 4. Boundary Compliance (Highest Priority)

- [VERIFY] В репо реально соблюдаемо правило: **STEP 1.x read-only**.
  - Criteria:
    - изменения STEP 1.x запрещены процессом (review/branch rules/CI), либо
    - явно помечены как нарушение канона и блокируются.

- [PASS] Единственная точка контроля открытия новых позиций: `before_open_position(symbol, strategy_id)`.
- [PASS] STEP 2.0 не управляет открытыми позициями; закрытие/ведение позиций остаётся в STEP 1.x.

---

## 5. FSM & Pause/Stop Semantics

- [PASS] FSM states зафиксированы:
  - `TRADING_ACTIVE`
  - `AUTO_PAUSED`
  - `HARD_STOPPED`

- [PASS] Auto-resume допускается только из `AUTO_PAUSED`.
- [PASS] После `HARD_STOPPED` автозапуск запрещён.

- [VERIFY] Единственный владелец переходов FSM: `TradingStateMachine`.
  - Criteria:
    - в коде/плане нет второго места, которое меняет `state` напрямую.

---

## 6. GateEngine Compliance

- [PASS] Gate contract зафиксирован: `ALLOW|VETO + reasons[2–3] + evidence`.
- [PASS] Allowed evidence sources ограничены (tech blocks / health / read-only market evidence / cooldown).
- [PASS] Forbidden evidence запрещено:
  - PnL и прибыльность,
  - неаудируемые эвристики,
  - “подглядывание” в стратегические внутренности STEP 1.x.

- [VERIFY] Gate не является “скрытым оркестратором”.
  - Criteria:
    - Gate возвращает решение,
    - transitions делает только `TradingStateMachine`,
    - Gate не меняет mode/state.

---

## 7. Command Surface & Risky Confirm

- [PASS] Все команды инициируются только человеком; UI/Telegram proxy-only.
- [PASS] `/status` safe и не требует подтверждения.
- [PASS] Risky команды требуют 2-step confirm (`да/yes`) с контекстной привязкой.

- [VERIFY] Confirm реально контекстный + TTL.
  - Criteria:
    - “да/yes” без armed-context не выполняет ничего,
    - одно подтверждение = одна команда,
    - таймаут отменяет команду.

---

## 8. SIM / Observability Non-Control

- [PASS] SIM не управляет REAL.
- [PASS] SIM evidence используется только read-only.

- [VERIFY] Нет “скрытого управления” через observability.
  - Criteria:
    - события/логи не запускают торговлю напрямую,
    - только явные triggers через `TradingStateMachine` по контракту.

---

## 9. Strategy Lock (1 coin = 1 strategy)

- [PASS] Lock semantics зафиксированы: lock держится до закрытия позиции.
- [VERIFY] Есть read-only сигнал “позиция закрыта” из STEP 1.x.
  - Criteria:
    - StrategyLockManager узнаёт о закрытии без вмешательства в STEP 1.x.

---

## 10. BNB Tech Ops

- [PASS] BNB auto-topup — техоперация, не стратегия.
- [PASS] При невозможности BNB:
  - новые сделки запрещены,
  - открытые доводятся до конца,
  - SIM продолжает анализ,
  - отправляется уведомление,
  - активируется `tech_block = BNB_LOW`.

- [VERIFY] Источники для BNBManager read-only и не требуют правок STEP 1.x.
  - Criteria:
    - BNBManager не лезет в стратегию/ордера,
    - выставляет только tech_block.

---

## 11. Notifications & Daily Report

- [PASS] Notification triggers зафиксированы:
  - stop,
  - pause reason change,
  - resume,
  - BNB block on/off.

- [VERIFY] Защита от “спама” при periodic Gate.
  - Criteria:
    - уведомления только при смене состояния/причин (diff-based).

---

## 12. GO / NO-GO Decision

### 12.1. Minimal GO Conditions (Hard)

GO разрешён только если выполняются ВСЕ пункты:

- [ ] `before_open_position(...)` — единственная точка контроля открытия
- [ ] `TradingStateMachine` — единственный владелец FSM transitions
- [ ] Risky confirm контекстный + TTL
- [ ] Gate evidence строго по контракту (без PnL/стратегии/эвристик)
- [ ] Реализация STEP 2.0 ведётся в новых модулях без правок STEP 1.x

### 12.2. NO-GO Rule

Если любой из пяти hard-пунктов нарушен — **NO-GO**.

---

## 13. Default Verdict

- Документально: `GO`
- Практически: `GO` после закрытия всех пунктов `VERIFY`

---

### ✔ Checklist Fixed
