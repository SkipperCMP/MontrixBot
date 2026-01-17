# Governance Decision: Auto Execution Allowed

## ID
GD_AUTO_EXECUTION_ALLOWED

## Status
FORBIDDEN BY DEFAULT

## Scope
MontrixBot — Auto-REAL

## Decision

Разрешить системе MontrixBot автономно
исполнять торговые операции **без ручного подтверждения**
при соблюдении всех условий STEP 2.x.

## Preconditions (Mandatory)

- Gate с evidence contract
- Explain trace для каждого действия
- VETO человека в любой момент
- HARD STOP с абсолютным приоритетом
- Полный audit trail
- Safe Mode без исключений

## Explicitly Allowed

- Autonomous execution
- FSM-based Auto-REAL
- Supervisor-only role человека

## Explicitly Forbidden

- Silent activation
- Implicit enable
- Обход STOP или VETO
- Execution без explainability

## Human Role Change

Человек переходит из роли executor
в роль supervisor.

## Warning

Данное решение является точкой
невозврата по ответственности и контролю
и должно приниматься отдельно.

---

Approved by: Governance
Date: TBD
