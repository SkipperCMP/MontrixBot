# Governance Decision: REAL Execution Enabled

## ID
GD_REAL_EXECUTION_ENABLED

## Status
ACCEPTED (upon commit)

## Scope
MontrixBot — REAL execution layer

## Decision

Разрешить системе MontrixBot исполнять торговые операции
на **реальные средства** (REAL mode) при строгом соблюдении
архитектурных и governance-инвариантов проекта.

Данное решение **НЕ разрешает** автономное исполнение
без участия человека.

## Explicitly Allowed

- Использование REAL-модулей (Binance Spot API)
- Исполнение сделок на реальные средства
- Исполнение **только через Manual Confirm Surface**
- Применение Gate, SAFE MODE, risk limits
- Audit / Explain / Journal
- Snapshot-based UI (read-only)

## Explicitly Forbidden

- Auto-execution без ручного подтверждения
- Batch execution без confirm
- Обход SAFE MODE или Gate
- Live monitoring REAL-состояния
- Любые implicit approval механизмы

## Responsibility

Финансовая ответственность полностью лежит
на владельце системы.

Допустимые потери и лимиты определяются
отдельным Governance Decision.

## Notes

Данное решение разрешает **исполнение**,
но не изменяет роль человека:
человек остаётся исполнителем и
последней точкой ответственности.

---

Approved by: Governance
Date: TBD
