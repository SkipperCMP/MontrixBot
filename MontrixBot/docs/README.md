# README — точка входа в документацию MontrixBot

Данный файл является **обязательной точкой входа**
в документацию проекта MontrixBot.

Любое чтение, анализ или изменение документов проекта
**ДОЛЖНО начинаться с этого файла**.

Если порядок, роли или ограничения,
описанные в README, нарушаются —
интерпретация документации считается некорректной.

## Роль README

README:
- не описывает архитектуру,
- не вводит новых правил,
- не заменяет Governance,

НО:

- фиксирует **порядок чтения**,
- фиксирует **типы документов**,
- фиксирует **правила интерпретации**.

README является обязательным
мета-контрактом чтения документации.

Все документы проекта образуют иерархию,
определяемую их типом и порядком чтения.

# MontrixBot Documentation Index

## Полный индекс документов (12 файлов)

### Управляющие и процессные документы
- docs/00_governance/MontrixBot_Governance.md
- docs/00_governance/MontrixBot_Decision_Flow.md

### Vision
- docs/01_vision/MontrixBot_Internal_Vision.md

### Roadmaps
- docs/02_roadmaps/MontrixBot_Master_Roadmap.md
- docs/02_roadmaps/MontrixBot_Product_Roadmap.md

### Rules / Filters
- docs/03_rules/MontrixBot_MasterRules.md
- docs/03_rules/MontrixBot_Feature_Intake.md

### Overview / Contracts
- docs/04_overview/MontrixBot_Overview.md
- docs/04_overview/MontrixBot_Strategies_Canonical_RU.md

### Reference / Analytics
- docs/05_reference/MontrixBot_Best_Patterns.md
- docs/05_reference/MontrixBot_SIM_Analytical_Framework.md

## Типы документов и их роль

В документации MontrixBot используются следующие типы документов:

- **GOVERNANCE** — определяет иерархию и порядок принятия решений  
- **VISION** — отвечает на вопрос «зачем существует проект»  
- **ROADMAP (Master)** — определяет допустимый порядок развития  
- **ROADMAP (Product)** — описывает планируемое содержание версий  
- **RULES** — архитектурные и процессные инварианты реализации  
- **CONTRACT** — детерминированные спецификации (стратегии, взаимодействия)  
- **PROCESS** — порядок мышления и проверки допустимости решений  
- **FILTER** — входной контроль идей и фич  
- **REFERENCE** — справочные и аналитические материалы

Документы нижнего типа:
- не могут переопределять документы верхнего типа,
- не могут расширять их задним числом,
- не могут использоваться как аргумент допустимости изменений.

## Порядок чтения (обязательный)

1. docs/00_governance/MontrixBot_Governance.md  
2. docs/01_vision/MontrixBot_Internal_Vision.md  
3. docs/02_roadmaps/MontrixBot_Master_Roadmap.md  
4. docs/02_roadmaps/MontrixBot_Product_Roadmap.md  
5. docs/03_rules/MontrixBot_MasterRules.md  
6. docs/04_overview/MontrixBot_Overview.md  
7. docs/00_governance/MontrixBot_Decision_Flow.md  
8. docs/04_overview/MontrixBot_Strategies_Canonical_RU.md  
9. docs/06_concepts/STEP_2_PLUS_CONCEPT.md
10. docs/06_concepts/STEP_2_0_SCOPE_CHECKLIST.md
12. docs/06_concepts/*
13. docs/07_governance_decisions/*
Примечание: список выше — это порядок чтения основных уровней.
Остальные документы из "Полного индекса" читаются по необходимости
в соответствии с их типом (FILTER / REFERENCE).

Документы должны читаться
**строго в указанном порядке**.

Документ, прочитанный без понимания
вышестоящих документов,
не может быть корректно интерпретирован.

Следующие примечания приведены
для контекста и ориентации читателя.

Они не заменяют и не переопределяют
Master Rules или Strategy Contracts.

Примечание: запуск системы (engine) и разрешение торговых действий
(trade arming) являются разными уровнями управления.

SIM и REAL логически разделены.
SIM не управляет REAL.
Передача информации возможна
только в форме наблюдательных
ScoutNotes.

UI control-surface минимален: SIM Start/Stop и REAL Start/Stop (ARM/DISARM).
Debug/Dev элементы не являются частью основного пользовательского интерфейса.

## Статус проекта (канонический)

- STEP 1.x — **ЗАКРЫТ** и зафиксирован как канонический фундамент.
- STEP 2.x (Auto-REAL) — **РАЗРЕШЁН GOVERNANCE-РЕШЕНИЕМ**, реализация **НЕ НАЧАТА**.

Важные замечания:
- STEP 2.x существует только как **концептуальный и разрешённый Governance-уровень**.
- Реализация STEP 2.x запрещена без отдельного явного решения на исполнение.
- STEP 1.x **не подлежит изменению**, расширению или ретроактивной адаптации под STEP 2.x.
- **Единственный легальный мост** между STEP 1.x и STEP 2.x:
  `docs/07_governance_decisions/GD_STEP_2_X_AUTO_REAL.md`.
