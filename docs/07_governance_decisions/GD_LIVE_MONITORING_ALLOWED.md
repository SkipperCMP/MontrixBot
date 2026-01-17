# Governance Decision: Live Monitoring Allowed

## ID
GD_LIVE_MONITORING_ALLOWED

## Status
OPTIONAL / PENDING

## Scope
MontrixBot — UI / Monitoring

## Decision

Разрешить live read-only мониторинг REAL-состояния
при строгом соблюдении ограничений,
исключающих создание скрытого контура управления.

## Explicitly Allowed

- Read-only мониторинг REAL
- Sampling / delayed view
- Изолированный monitoring layer

## Mandatory Restrictions

Live monitoring НЕ МОЖЕТ:
- генерировать сигналы
- ускорять или подталкивать confirm
- изменять state
- взаимодействовать с SIM decision loop

## Explicitly Forbidden

- Использование live monitoring как control surface
- Связывание live view с execution UX
- Любые формы soft-automation через человека

## Risk Acknowledgement

Признаётся наличие:
- психологического давления
- поведенческого риска
- снижения дисциплины

Решение принимается осознанно.

---

Approved by: Governance
Date: TBD
