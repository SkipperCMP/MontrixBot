# Governance Decision: Assisted REAL Allowed

## ID
GD_ASSISTED_REAL_ALLOWED

## Status
ACCEPTED (upon commit)

## Scope
MontrixBot — Assisted REAL mode

## Decision

Разрешить режим Assisted REAL, при котором:

- SIM формирует intent / proposal
- Человек **явно подтверждает** каждое исполнение
- REAL остаётся неактивным без confirm

## Explicitly Allowed

- Intent / proposal loop
- Explain / why_not reasoning
- Manual Confirm Surface как обязательный шаг
- SAFE MODE, Gate, risk limits
- Snapshot / Journal / Replay

## Explicitly Forbidden

- Исполнение без confirm
- Автоповторы без нового подтверждения
- Silent execution
- Любая форма implicit consent
- Live monitoring REAL

## Human Role

Человек остаётся:
- исполнителем
- носителем ответственности
- точкой принятия риска

## Notes

Assisted REAL не является Auto-REAL
и не изменяет архитектурную роль человека.

---

Approved by: Governance
Date: TBD
