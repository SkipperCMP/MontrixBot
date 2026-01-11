# UI_DATA_CONTRACTS.md  
MontrixBot — UI Data Contracts (read-only)

Статус: ACTIVE  
Область: UI ↔ Runtime (только чтение)

ВАЖНО:
Этот документ НЕ задаёт формат runtime,
НЕ требует изменений логов и
НЕ влияет на исполнение.

Он описывает, КАК UI читает уже существующие runtime-артефакты.

---

## 0. Общие принципы

1. UI строго read-only к REAL  
2. UI не инициирует торговые действия  
3. UI не интерпретирует решения — только отображает  
4. Все решения имеют источник и timestamp  
5. История событий — append-only  

---

## 1. runtime/status.json — System Status

### Назначение
Единый агрегированный статус системы для:
- вкладки Main
- вкладки Explain
- части Settings
- расчёта “age” (свежести состояния)

### Минимально читаемый контракт

json
{
  "fsm": "TRADING_ACTIVE | HARD_STOPPED | ...",
  "mode": "MANUAL_ONLY | AUTO_SHADOW | AUTO_FULL | ...",
  "policy_hard_stop_active": true,
  "why_not": [
    "MANUAL_STOP",
    "MODE_MANUAL_ONLY",
    "HARD_STOP"
  ],
  "ts_utc": "2026-01-04T21:37:55.947771+00:00",
  "source": "runtime/status.json",
  "gate": {
    "decision": "ALLOW | VETO",
    "reasons": ["MODE_MANUAL_ONLY", "HARD_STOP"],
    "evidence": ["status:ts=...", "policy:file=..."]
  },
  "gate_last": {
    "decision": "ALLOW | VETO",
    "reasons": ["..."],
    "evidence": ["..."],
    "ts_utc": "2026-01-04T21:37:55.947771+00:00"
  }
}

Использование в UI
Main
fsm, mode
gate.decision
why_not
ts_utc → age
Explain
why_not
gate / gate_last
Settings
mode
policy_hard_stop_active

2. runtime/events.jsonl — Event Spine
Назначение
Единая лента событий для:
Journal
Explain (последнее решение SIM)
Trade Viewer (через correlation_id)
Формат: JSON Lines
Общий контракт события
json
{
  "ts_utc": "2026-01-04T21:37:55.947771+00:00",
  "event": "EVENT_TYPE",
  "cls": "SIM | SYS | REAL",
  "correlation_id": "B097227FE53323AF",
  "payload": {}
}
2.1 SIM_DECISION_JOURNAL
json
{
  "hypothesis": "Range regime conflict",
  "signals": ["Conflicting signals"],
  "confidence": 0.41,
  "recommended_action": "HOLD | BUY | SELL",
  "strategy": "StrategyName",
  "notes": "optional"
}
Использование
Journal → таблица SIM решений
Explain → последнее решение SIM
2.2 System Events (cls = SYS)
Используются для:
Journal → System Events
Main → Notices / Alerts
Примеры:
смена режима
HARD_STOP
применение конфигураций

3. Связка Explain ↔ Journal
Explain:
берёт WHY NOT и Gate из status.json
берёт последнее SIM_DECISION_JOURNAL из events.jsonl
НЕ смешивает роли SIM и Gate

4. Trade Viewer (через события)
Trade Viewer:
не управляет сделкой
восстанавливает историю по events.jsonl
использует correlation_id
Отображает:
ENTRY / STOP / EXIT
timeline
контекст SIM + Gate

5. Конфигурации (inspection-only)
Если присутствуют конфигурационные файлы:
UI читает их как read-only
любые изменения фиксируются событиями
UI не применяет конфиги напрямую

6. Явные запреты
UI_DATA_CONTRACTS.md:
не задаёт формат логов
не добавляет поля
не влияет на runtime
не разрешает управление REAL

7. Итог
status.json — состояние и разрешения
events.jsonl — история и решения
UI — инспектор и объяснитель
Документ используется совместно с README_UI.md