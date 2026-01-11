⚠️ Статус документа

Данный документ:
- определяет контракты стратегий,
- НЕ даёт разрешения на их внедрение,
- НЕ определяет этапы реализации.

Разрешение на внедрение стратегии
определяется исключительно Master Roadmap.

# MontrixBot — Strategies Specification (Canonical)

**Статус:** Canonical / Governance  
**Язык:** Русский (английский используется только для идентификаторов)

Этот документ определяет торговые стратегии MontrixBot как
**детерминированные торговые контракты**.

Документ имеет приоритет над реализацией.
Любые расхождения трактуются как ошибка реализации.

---
==================================================INVARIANTS==================================================

### Global Invariants (Hard Rules)

- Strategy не может обходить Modules
- VETO любого Module финален
- Strategy не определяет market regime
- REAL корректно работает при SIM = OFF
- Zero active strategies — допустимое состояние
- Усреднение запрещено, если не указано явно
- Любая позиция обязана иметь exit-path

### MoonBot Non-Dependency Rule

MoonBot strategies, parameters, and execution logic are NOT used in MontrixBot.
Any resemblance is conceptual only.
All strategies are specified as deterministic contracts
under MontrixBot Modules, Orchestrator, and REAL execution rules.

==================================================ACCEPTANCE_CHECKLIST==================================================

Before Strategy becomes Active:

- [ ] Работает при SIM = OFF
- [ ] Все entry проходят Modules
- [ ] Нет silent-fail сценариев
- [ ] Partial fill обработан
- [ ] Data-staleness → безопасный halt
- [ ] PANIC → controlled close
- [ ] Metrics пишутся

==================================================ORCHESTRATOR_PRIORITY==================================================

Default Priority (highest → lowest):
1. Emergency / Exit flows
2. Trend strategies
3. Reversion strategies
4. Scalping strategies

---

## Strategies / Modules / Orchestrator — Canonical Separation (REAL Layer)

### Definitions (Hard Rules)

**Strategy**
- Включаемая/выключаемая сущность.
- Может открывать позиции (имеет entry) и обязана иметь полный lifecycle сделки.
- Не имеет права обходить safety/exec контуры.

**Module (Always-On)**
- Всегда включён, пока работает REAL.
- Не открывает позиции и не выбирает активы.
- Может запретить (veto) любое действие стратегии или инициировать экстренный выход.

**Orchestrator**
- Всегда включён, пока работает REAL.
- Определяет режим рынка (regime), выдаёт/запрещает “право попытки” стратегиям.
- Разруливает конфликты стратегий и лимиты параллелизма.

**Правило:** *Strategy decides WHAT to do; Modules decide WHETHER it is allowed; Orchestrator decides WHO gets a turn.*

---

## Modules (Always-On) — Safety & Execution Checklist

Любой модуль может выдать **VETO**. VETO финален: действие не выполняется.

### A) Data Integrity & Latency
1) **MarketDataHealthGuard**
- stale data / разрыв стрима / пропуски
- on_fail: запрет новых ордеров, отмена активных entry, при повторе → ERROR_HALT

2) **LatencyGuard**
- задержка трейдов/квотов/ответов биржи выше порога
- on_fail: запрет входов, ограничение модификаций, при росте → SAFE

3) **SymbolMetaGuard**
- тик-сайз/лот-сайз/precision корректны
- on_fail: ERROR_HALT (невозможно безопасно торговать)

### B) Execution Safety
4) **OrderLifecycleSupervisor**
- нет “потерянных” ордеров; все статусы согласованы
- on_fail: stop new orders → reconcile → ERROR_HALT при расхождении

5) **RetryPolicyEnforcer**
- единые лимиты попыток/бэкофф, защита от API-spam
- on_fail: cooldown / запрет повторов

6) **PartialFillHandler**
- deterministic policy: cancel remainder / unwind / accept min_fill_ratio

7) **AtomicityHandler**
- FAILSAFE_UNWIND для атомарных входов (если стратегия требует)

8) **ExchangeErrorClassifier**
- нормализация ошибок: reject, rate-limit, insufficient balance, post-only, etc.

### C) Market Safety Guards
9) **SpreadGuard (bid/ask)**
- запрет входа/модификаций при spread > max_spread_pct

10) **SlippageGuard**
- запрет агрессивного входа/выхода при ожидаемом slippage > max

11) **LiquidityGuard**
- min depth, thin book / vacuum detection
- on_fail: запрет входов; при открытой позиции → ускоренный выход policy

12) **VolatilityGuard / ImpulseGuard**
- “рынок проснулся”: всплеск скорости/волы/объёма
- on_fail: запрет новых входов; при позиции → impulse-exit

### D) Risk & Portfolio Controls
13) **PortfolioRiskManager**
- equity, drawdown, exposure caps; emergency portfolio SL
- on_fail: SAFE/PANIC policy + controlled close

14) **StrategyRiskManager**
- max loss per strategy/day, max trades, cooldowns
- on_fail: veto входов, перевод стратегии в COOLDOWN/IDLE

15) **PositionSizerEnforcer**
- гарантирует верхние лимиты размера позиции (pct equity, fixed notional, microvolume)

### E) Operational
16) **ModeGate (SAFE/PANIC)**
- SAFE: входы запрещены
- PANIC: инициировать controlled close / emergency exit policy

17) **KillSwitch**
- мгновенно: stop new orders + cancel active + (optional) exit open positions → ERROR_HALT

18) **AuditLogger (Mandatory)**
- событийный лог (events) + причины veto

19) **MetricsSink (Mandatory)**
- метрики исполнения и риска

**Minimal MUST-HAVE для допуска в Active:** 1,4,9,10,13,16,18,19.

---

## Orchestrator (REAL) — Permissions & Conflicts

### Responsibilities
- Market regime classification (минимальный baseline в REAL).
- Выдача разрешений стратегиям: кто может “попытаться” на этом тике.
- Mutual exclusion (стратегии не должны конфликтовать).
- Concurrency limits (по умолчанию: 1 активная позиция на всё REAL, если не указано иначе).

### Default Conflict Rules (Hard)
- Одновременно активной может быть **только одна** позиция (global max 1), если не задан иной режим.
- **Reversion**-стратегии (Impulse Catcher / Range Reversion / Spread Scalper) не торгуют в TREND.
- **Trend/Momentum**-стратегии (Trend Rider / Momentum Breakout) не торгуют в FLAT.
- При **PANIC**: все стратегии переводятся в EXITING/CONTROLLED_CLOSE по policy.

---

## Interaction Contract (REAL Loop)

Стратегии **не ставят ордера напрямую**. Они формируют **Intent**, который проходит через Modules и исполняется ExecutionService.

### Intent Types
- NOOP
- PLACE_ENTRY(order_spec)
- MODIFY_ORDER(mod_spec)
- CANCEL_ORDER(order_id)
- START_EXIT(exit_plan)
- EMERGENCY_EXIT(reason)
- REQUEST_ERROR_HALT(reason)

### Canonical Order of Operations (per tick)
1) **Data ingest** → MarketDataHealthGuard
2) **Orchestrator.update_regime** → (optional) regime_changed
3) **Global risk pre-check** → ModeGate + PortfolioRiskManager
4) **Select candidates** → Orchestrator.select_strategies (enabled + permissions + conflicts)
5) **strategy.step()** → produce Intent
6) **Modules validate(Intent)** → veto or allow
7) **ExecutionService.execute(Intent)** → OrderLifecycleSupervisor track
8) **Post-trade handling** → PartialFillHandler / AtomicityHandler
9) **Strategy state update** → state_transition events

### VETO Rule
Если любой модуль вернул veto:
- действие **не исполняется**
- пишется event `module_vetoed`
- стратегия применяет policy: NOOP / COOLDOWN / EXIT (в зависимости от intent)

---

## Mandatory Events (System-Level)

### Orchestrator / Modes
- system_mode_changed {from,to,reason}
- regime_changed {scope:market|asset, from,to, reason_summary}
- strategy_enabled / strategy_disabled {strategy_id}
- strategy_permission_granted / strategy_permission_denied {strategy_id, reason}

### Modules (Veto / Health)
- module_vetoed {module, strategy_id, intent_type, reason, snapshot}
- data_stale_detected {age_sec}
- latency_exceeded {latency_ms}
- liquidity_vacuum_detected {depth, spread, ...}
- spread_spike_detected {spread_pct}
- slippage_risk_exceeded {expected_pct}
- risk_limit_hit {limit_name, value, action}
- error_halt {scope:SYSTEM|STRATEGY, error_code, context}

### Execution (Unified)
- order_submitted / order_modified / order_cancelled
- order_rejected / order_partially_filled / order_filled
- position_opened / exit_started / position_closed

**Note:** каждая стратегия дополнительно обязана иметь свой список events/metrics (см. разделы стратегий ниже).

---

## Mandatory Metrics (System-Level)

**System**
- equity, drawdown, exposure
- open_positions_count, open_orders_count
- time_in_mode (NORMAL/SAFE/PANIC)

**Execution Quality**
- slippage_entry_avg, slippage_exit_avg
- reject_rate, partial_fill_rate, timeout_rate
- time_to_fill_ms

**Per Strategy (minimum)**
- strategy_pnl, trades_count, winrate, avg_trade_duration
- cooldown_time_total
- time_in_state (по каждому состоянию)

---

## UI / Controls (Governance)

Разрешённые тумблеры:
- Start/Stop SIM
- Start/Stop REAL
- Strategy ON/OFF (только для стратегий)

Запрещено:
- отключение Modules
- ручное “управление” решениями стратегии через UI (UI = display-only)

**Invariant:**  
REAL-исполнение корректно работает при `SIM = OFF`.  
SIM не может:
- инициировать вход
- изменять параметры REAL напрямую
- отменять решения REAL

## Связь со структурой проекта

Данный документ является канонической спецификацией стратегий,
но не является управляющим.

Все стратегии обязаны:
- соответствовать Master Rules,
- внедряться только в разрешённых STEP’ах,
- не переопределять решения Governance и Roadmap.


==================================================1==================================================

### Strategy: Rocket + 2 Anchors

#### Purpose
Торговля высоковолатильной монетой (“Rocket”)
в составе атомарной портфельной тройки
(1 Rocket + 2 Anchors) с контролем риска,
фиксацией прибыли и адаптацией параметров
к текущему рынку.

Стратегия работает **только при наличии полной тройки**.
Без тройки торговля не начинается.

---

#### Scope
- Type: Portfolio (Atomic Triple)
- Mode: REAL
- Structure:
  - Rocket — 1 высоковолатильная монета
  - Anchor A — стабильная монета
  - Anchor B — стабильная монета

---

#### Core Principle (Atomicity)
- Торговля начинается только после формирования тройки
- Все операции выполняются исключительно внутри тройки
- Замена возможна только внутри роли (Rocket ↔ Rocket, Anchor ↔ Anchor)
- Невозможность восстановления или замены ⇒ Controlled Close

---

#### State Machine (Deterministic)

Стратегия является конечным автоматом со следующими состояниями:

- IDLE: стратегия выключена или тройка не сформирована
- TRIPLE_FORMED: тройка выбрана, но позиции ещё не открыты
- ENTERING: выполняется атомарный вход (3 ордера)
- ACTIVE: тройка открыта и управляется стратегией
- RESTORE_PENDING: один из элементов тройки выбыл, идёт попытка восстановления
- REPLACE_PENDING: восстановление невозможно, идёт поиск/вход замены
- CONTROLLED_CLOSE: закрытие стратегии без новых покупок
- CLOSED: все позиции закрыты, стратегия завершена
- ERROR_HALT: остановка из-за критической ошибки исполнения

Разрешённые переходы:

- IDLE -> TRIPLE_FORMED (тройка сформирована и прошла фильтры)
- TRIPLE_FORMED -> ENTERING (старт атомарного входа)
- ENTERING -> ACTIVE (все 3 позиции открыты в допустимых отклонениях)
- ENTERING -> IDLE (атомарный вход не удался, позиции не открыты)
- ACTIVE -> RESTORE_PENDING (элемент выбыл, есть шанс восстановить)
- RESTORE_PENDING -> ACTIVE (восстановление выполнено)
- RESTORE_PENDING -> REPLACE_PENDING (восстановление невозможно)
- REPLACE_PENDING -> ACTIVE (замена выполнена)
- RESTORE_PENDING -> CONTROLLED_CLOSE (restore+replace невозможны)
- REPLACE_PENDING -> CONTROLLED_CLOSE (replace не удался)
- ACTIVE -> CONTROLLED_CLOSE (глобальный риск, SAFE, emergency SL)
- CONTROLLED_CLOSE -> CLOSED (все позиции закрыты)
- * -> ERROR_HALT (критическая ошибка исполнения/данных)

Инварианты state machine:
- В IDLE, TRIPLE_FORMED, CONTROLLED_CLOSE запрещены новые входы в рынок (кроме необходимых для восстановления/замены в pending-состояниях).
- В CONTROLLED_CLOSE запрещены restore/replace и любые новые покупки.
- В ACTIVE тройка обязана быть полной; если не полная — состояние должно перейти в RESTORE_PENDING/REPLACE_PENDING.
- ERROR_HALT требует ручного вмешательства/сброса.

---
#### Preconditions (Global Filters)

Стратегия **НЕ АКТИВНА**, если:
- SAFE MODE = ON
- глобальная торговля запрещена
- Equity Drawdown ≥ 20 %

**Liquidity Filter**
- Min orderbook depth (top 1%): ≥ 50 000 USDT

**Volume Filter**
- 24h Volume:
  - Rocket ≥ 10 000 000 USDT
  - Anchors ≥ 50 000 000 USDT

**Spread Filter**
- Max spread:
  - Rocket ≤ 0.30 %
  - Anchors ≤ 0.10 %

**Time Session Filter**
- Trading hours: 00:00 – 23:59 UTC
- Blocked periods:
  - первые 5 минут после открытия суток

**Asset Lists**
- Whitelist Anchors: USDT, USDC, FDUSD, DAI
- Blacklist: Low-liquidity / delisted / leveraged tokens

---

## 1️⃣ Triple Selection (Pre-Trade)

Перед первой покупкой бот обязан:
- выбрать Rocket по волатильности и импульсу
- выбрать 2 Anchors из Whitelist
- проверить корреляцию Rocket ↔ Anchors < 0.6
- зафиксировать тройку как Active Triple

Если тройка не собрана — **не совершается ни одной сделки**.

---

## 2️⃣ Initial Entry (Atomic Buy)

Покупка выполняется **ТОЛЬКО ВСЕЙ ТРОЙКОЙ**.

**Initial Allocation**
- Rocket: 20 % Equity
- Anchor A: 40 % Equity
- Anchor B: 40 % Equity

Если хотя бы один ордер не исполнен в течение 30 секунд —
все ордера отменяются.

---

## 3️⃣ Entry Rules (Re-Entry)

### Rocket Entry
Разрешена покупка Rocket, если:
- текущая доля Rocket < Target Allocation
- market regime = trend or high-vol
- нет активного cooldown

### Anchor Entry
Разрешена покупка Anchor, если:
- Anchor является частью Active Triple
- Anchor продан частично или полностью
- условия ликвидности и спреда соблюдены

---

## 4️⃣ Order Execution

- OrderType:
  - Rocket: Market
  - Anchors: Limit (timeout 20s)
- Retry Logic:
  - Max attempts: 3
  - Retry delay: 5s
- Partial Fills:
  - Allowed: Yes
  - Iceberg for Rocket: Yes (order split = 3)

---
#### Execution Failure Matrix (Mandatory)

Любая торговая операция должна обрабатываться через сценарии отказов.
Ниже — обязательные реакции стратегии.

1) Order Rejected (биржа отклонила ордер)
- ENTERING:
  - отменить все ордера тройки
  - если какие-то частично исполнены: перейти в FAILSAFE_UNWIND (см. п.5)
  - иначе: TRIPLE_FORMED -> IDLE с penalty 60 мин
- ACTIVE:
  - если это restore/replace ордер: перейти в CONTROLLED_CLOSE

2) Partial Fill (частично исполнен)
- ENTERING:
  - если суммарная недозаполненность > 20% по любому из 3 ордеров через 30 сек:
    - отменить остаток
    - перейти в FAILSAFE_UNWIND
  - иначе:
    - продолжить добор остатка через retry (до 3 попыток)
- ACTIVE:
  - частичные исполнения допустимы, но обязателен reconcile балансов (см. Observability)

3) Timeout / No Fill
- ENTERING:
  - отменить ордер
  - retry до 3 раз
  - если не удалось: FAILSAFE_UNWIND
- ACTIVE:
  - для limit-ордеров (anchors): fallback на market, если maxSpread соблюдён
  - иначе: отмена и ожидание следующего окна

4) Slippage выше допуска
- Rocket: max slippage 0.50%
- Anchors: max slippage 0.20%
Если превышено:
- отменить текущий ордер
- cooldown 30 мин
- повторить не более 1 раза
- при повторном превышении: CONTROLLED_CLOSE

5) FAILSAFE_UNWIND (аварийный откат атомарного входа)
Если ENTERING не завершился атомарно, но часть позиций уже открыта:
- цель: выйти в “безопасный плоский” портфель без добора
- действие:
  - закрыть все открытые части позиций рынка (market) с ограничением maxSlippage
  - если maxSlippage нарушен: закрывать частями (iceberg=3) до 2 минут
  - после закрытия: ENTERING -> IDLE + penalty 120 мин

6) Balance / Position Mismatch (баланс ≠ ожидаемое)
- немедленно stop new orders
- выполнить reconcile (см. Observability)
- если mismatch не исправлен: ERROR_HALT

---

## 5️⃣ Position Management

### Scale-In (Add Position)
- Rocket:
  - Max Adds: 2
  - Add threshold: −3 % от последней покупки
- Anchors:
  - Only to restore target allocation

### Partial Sell
- Rocket:
  - Partial TP at +8 %
- Anchors:
  - Partial sell запрещён (якоря — стабилизация)

---

## 6️⃣ Replacement Policy

### Restore
- попытка восстановить тот же актив
- Max restore attempts: 2
- Restore window: 30 минут

### Replace
Если restore невозможен:
- поиск замены в рамках роли
- replacement cooldown: 60 минут
- replacement allowed only if:
  - не увеличивает риск
  - проходит все filters
  - корреляция с оставшимися активами < 0.6
- Max replacements per triple: 1

### Failure
Если restore и replace невозможны:
→ стратегия переходит в Controlled Close

---

## 7️⃣ Exit Logic

### Take Profit
- Rocket:
  - Partial TP: +8 %
  - Full TP: +15 %
- Прибыль перераспределяется в Anchors

### Stop Loss
- Rocket Hard SL: −6 %
- Strategy Max Loss: −12 %
- Portfolio emergency SL: −20 %

### Trailing Exit
- Enabled: Yes
- Trailing start: +5 %
- Trailing distance:
  - Low vol: 2 %
  - High vol: 4 %
- Break-Even:
  - Activate at +4 %

---

## 8️⃣ Penalties & Cooldowns (Risk Governance)

- Cooldown after loss: 60 минут
- Cooldown after replacement: 120 минут
- Ignore new Rocket entries after:
  - 2 consecutive losses
- Max trades per triple: 10

---

## 9️⃣ Parameterization & Adaptation

**Adaptive Parameters**
- Target Rocket Allocation: 15–25 %
- Entry Size: 5–10 %
- Trailing Distance: 2–4 %
- Cooldown Duration: 30–120 мин
- Default Target Rocket Allocation: 20 %

**Update Rules**
- Adaptation frequency: ≤ 1 per 30 мин
- Volatility bucket based
- Risk non-increasing invariant enforced

---

## 🔟 Risk Limits

- Max Loss per Trade: 2 %
- Max Loss per Strategy: 12 %
- Max Portfolio Drawdown: 20 %

On breach:
- disable new entries
- Controlled Close if needed

---

#### Observability & Audit Trail (Mandatory)

Стратегия обязана писать события (events) и метрики (metrics).
Без этого стратегия считается неуправляемой и не допускается в Active.

Events (минимальный список):
- triple_selected {rocket, anchorA, anchorB, timestamp, reason_summary}
- state_transition {from, to, reason}
- order_submitted {asset, side, type, qty, price_limit, attempt}
- order_filled {asset, side, qty, avg_price, slippage, partial=true/false}
- order_cancelled {asset, reason}
- entry_completed {triple_id, allocations}
- restore_started / restore_success / restore_failed {asset, reason}
- replace_started / replace_success / replace_failed {role, candidate, reason}
- risk_limit_hit {type, value, action}
- controlled_close_started / completed
- reconcile_started / completed {diff_summary}
- error_halt {error_code, context}

Metrics (минимальный список):
- equity, strategy_pnl, pnl_daily
- rocket_allocation%, anchor_allocation%
- max_drawdown%, consecutive_losses
- fill_rate%, avg_slippage, rejection_rate
- trades_count, replacements_count, restore_count
- time_in_state (по каждому состоянию)

Audit requirements:
- каждая смена параметров должна писать:
  parameter_change {name, old, new, reason_bucket, cooldown_ok=true/false}
- хранить историю последних 100 событий по стратегии

---
## 1️⃣1️⃣ SIM / REAL Split

**SIM**
- подбор Rocket и Anchors
- анализ режимов рынка
- предложения по параметрам и замене
- ScoutNotes (no commands)

**REAL**
- финальный выбор тройки
- исполнение ордеров
- контроль риска
- работа при SIM = OFF (safe defaults)

---

#### Stress Tests & Acceptance Criteria (Mandatory)

Стратегия допускается в статус Active только после прохождения тестов ниже
(симуляция/песочница/исторические прогоны).

Сценарии рынка:

1) FLAT (низкая волатильность, диапазон)
- ожидание: стратегия не пересобирает тройку часто, не совершает частые входы
- критерий: trades_count низкий, PnL около 0, drawdown минимальный

2) SAW (пила, ложные импульсы)
- ожидание: не более 2 убыточных входов подряд до cooldown
- критерий: consecutive_losses <= 2, затем cooldown активируется
- критерий: max strategy loss не превышен

3) DUMP (резкий обвал)
- ожидание: Rocket закрывается по SL/portfolio stop, стратегия переходит в close
- критерий: max portfolio drawdown не превышен
- критерий: после dump нет докупок (no new buys)

4) FAKE PUMP (памп → резкий разворот)
- ожидание: частичная фиксация + трейлинг/BE защищают результат
- критерий: worst-case результат не хуже ограниченного минуса
- критерий: profit фиксируется в anchors

Сценарии исполнения:

5) ENTERING partial fill
- ожидание: FAILSAFE_UNWIND с выходом в плоский портфель
- критерий: после unwind нет открытых остатков позиций

6) Order reject / API errors
- ожидание: no new orders, retry policy, затем close/penalty
- критерий: нет бесконечных попыток (attempts <= 3)

7) Slippage spike
- ожидание: отмена/ожидание/close при повторе
- критерий: slippage limits соблюдаются или стратегия уходит в close

Acceptance (hard):
- Нет нарушений инвариантов Atomicity
- Нет новых покупок в CONTROLLED_CLOSE
- SIM=OFF режим запускается с safe defaults и работает корректно
- Все mandatory events/metrics присутствуют

---

#### Compliance
- MasterRules: ✔
- SIM / REAL isolation: ✔
- Indicator scope: ✔
- REAL works with SIM = OFF: ✔

---

#### Status
Active (v1.5 candidate)



==================================================2==================================================

### Strategy: Impulse Catcher (Moon-Family)

#### Purpose
Торговля быстрых импульсных «прострелов» (в первую очередь вниз)
с целью поймать отскок/возврат цены после краткосрочного дисбаланса ликвидности.

Стратегия основана на идеях MoonShot / MoonHook / MoonStrike,
но реализована как **детерминированный торговый контракт**
(а не «стратегия=ордер»).

---

#### Scope
- Type: Single-Asset (Event-driven / Impulse Reversion)
- Mode: REAL (обязателен SIM=OFF режим)
- Market: Spot by default (Futures optional in later versions)
- Concurrency:
  - Default: max 1 active position одновременно
  - Watchlist может быть шире, но вход — строго по лимитам стратегии

---

#### Core Principle
- Стратегия управляет **одной позицией/одним активом** в рамках одного цикла сделки.
- Вход реализуется через единый Entry Engine с тремя режимами:
  - SHOT: плавающий лимитный вход ниже рынка с управляемым коридором
  - HOOK: event-based детект импульса → лимитный вход в коридоре
  - STRIKE: быстрый snap-entry после подтверждённого детекта
- Режимы — **варианты entry**, а не разные стратегии.

---

#### State Machine (Deterministic)

Состояния:
- IDLE: стратегия выключена или условия не позволяют сканировать рынок
- SCANNING: мониторинг watchlist и ожидание сетапа/детекта
- ARMED: сетап найден, выбран режим входа (SHOT/HOOK/STRIKE)
- ORDER_PLACED: выставлен buy-ордер
- ORDER_ADJUSTING: перестановка buy-ордера внутри коридора (SHOT/HOOK)
- PARTIALLY_FILLED: частичное исполнение buy-ордера
- POSITION_OPEN: позиция открыта, действует модуль управления
- EXITING: выполняются закрывающие ордера (TP/SL/time-stop/emergency)
- CLOSED: позиция закрыта, цикл завершен
- ERROR_HALT: критическая ошибка исполнения/данных

Разрешённые переходы:
- IDLE -> SCANNING (разрешено торговать, нет глобальных блокировок)
- SCANNING -> ARMED (detector fired + asset passed filters)
- ARMED -> ORDER_PLACED (выставлен buy-ордер)
- ORDER_PLACED -> ORDER_ADJUSTING (для SHOT/HOOK при активном коридоре)
- ORDER_PLACED -> PARTIALLY_FILLED (получен partial fill)
- ORDER_PLACED -> POSITION_OPEN (buy полностью исполнен)
- ORDER_ADJUSTING -> ORDER_PLACED (коридор/перестановка завершена)
- PARTIALLY_FILLED -> POSITION_OPEN (добор завершён) или -> EXITING (отмена остатка + unwind)
- POSITION_OPEN -> EXITING (TP/SL/time-stop/emergency)
- EXITING -> CLOSED (позиция закрыта)
- * -> ERROR_HALT (критическая ошибка данных/исполнения)

Инварианты:
- В EXITING запрещены любые новые входы и перестановки buy-ордера.
- В ERROR_HALT запрещены новые ордера до ручного сброса.
- Максимум 1 активная позиция по умолчанию (если не указано иначе).
- Любой silent-fail запрещён: все сбои фиксируются событиями + действиями.

---

#### Preconditions (Global Filters)

Стратегия **НЕ АКТИВНА**, если:
- SAFE MODE = ON
- глобальная торговля запрещена
- Equity Drawdown ≥ 20 %

**Liquidity / Volume**
- Min orderbook depth (top 1%): ≥ 50 000 USDT
- 24h Volume: ≥ 10 000 000 USDT

**Spread**
- Max spread: ≤ 0.30 %

**Execution Reliability**
- Max exchange latency: ≤ 500 ms (если доступно)
- Запрещать вход при price-bug / stale quotes (если детектируется)

**Asset Lists**
- Whitelist / Blacklist применимы (наследуется из общих правил бота)

---

## 1️⃣ Entry Engine (Modes)

### SHOT Mode
**Идея:** держать лимитный buy ниже текущей цены и переставлять, если цена слишком близко подошла.

Параметры:
- shot_offset_pct: расстояние от текущей цены до buy (в %), всегда > 0
- shot_min_gap_pct: насколько цена может приблизиться к ордеру (в %), после чего ордер переставляется ниже
- shot_reprice_down_delay_ms: задержка перед перестановкой вниз
- shot_reprice_up_delay_ms: задержка перед перестановкой при росте (если применимо)
- shot_price_reference: BID | ASK | LAST
- shot_max_order_age_sec: максимальный срок жизни ордера до cancel + cooldown
- shot_max_active_orders: верхняя граница активных ордеров стратегии (по умолчанию 1)

Правила:
- buy_price = ref_price * (1 - shot_offset_pct)
- если (ref_price - buy_price)/ref_price < shot_min_gap_pct => переставить ордер на shot_offset_pct от текущей цены
- при превышении shot_max_order_age_sec => cancel + cooldown

---

### HOOK Mode
**Идея:** детект прострела → ставим buy в пределах события и ведём его в коридоре, зависящем от глубины детекта.

Параметры:
- hook_timeframe_ms: окно анализа скорости падения
- hook_detect_depth_pct: глубина прострела для детекта (мин.)
- hook_detect_depth_max_pct: глубина прострела (макс., 0=ignore)
- hook_anti_pump: учитывать «среднюю цену до детекта» для исключения детектов после пампа (YES/NO)
- hook_rollback_pct: % отката от глубины прострела для подтверждения (roll-back)
- hook_rollback_wait_ms: время удержания цены выше rollback
- hook_initial_level_pct: где ставить buy внутри прострела (может быть отрицательным)
- hook_corridor_width_pct: ширина коридора (0 = без управления ордером)
- hook_partfill_cancel_delay_ms: задержка отмены остатка после partial fill
- hook_reprice_down_delay_ms / hook_reprice_up_delay_ms: задержки перестановки ордера

Правила:
- detector фиксирует событие: depth, min_price, pre_event_price, rollback_level
- buy выставляется по hook_initial_level_pct относительно глубины (или по interpolate-правилу, если появится позже)
- если hook_corridor_width_pct > 0 => ордер управляется как в SHOT, но границы коридора вычисляются от event depth

---

### STRIKE Mode
**Идея:** как можно быстрее зайти после детекта прострела, иногда с микро-задержкой для подтверждения/углубления.

Параметры:
- strike_depth_pct: глубина прострела для детекта
- strike_min_volume: мин. объём на момент детекта (0=ignore)
- strike_buy_delay_ms: задержка между детектом и выставлением buy (может быть 0)
- strike_buy_level_pct: где покупать относительно глубины (0 = у дна; 50% = середина)
- strike_buy_relative: YES (от depth) / NO (от pre_event_price)
- strike_sell_level_pct: уровень продажи относительно глубины (а не от цены покупки)
- strike_wait_dip_confirm: ждать «признак окончания прострела» (YES/NO, с max wait)

Правила:
- detector фиксирует depth и min_price; optional: wait_dip_confirm
- через strike_buy_delay_ms выставляется buy на рассчитанном уровне
- заранее вычисляется sell_level по strike_sell_level_pct

---

## 2️⃣ Position Sizing (Risk)

- order_size_mode: FIXED_NOTIONAL | PCT_EQUITY
- max_position_pct_of_equity: верхняя граница
- optional micro-volume guard (MoonBot BuyOrderReduce analogue):
  - entry_max_notional_by_microvolume_ms: интервал для оценки среднего объёма
  - entry_min_notional: если итоговый размер ниже — вход запрещён

---

## 3️⃣ Position Management (Unified)

**Take Profit**
- tp_partial_enabled: YES/NO
- tp_partial_level_pct: уровень частичной фиксации
- tp_full_level_pct: уровень полной фиксации

**Stop Loss**
- hard_sl_pct: обязательный
- time_stop_sec: обязательный (если отскока нет)
- strategy_max_loss_pct: лимит потерь стратегии (сессия/день)
- portfolio_emergency_sl: глобальный хук (если есть)

**Trailing / Break-even (optional)**
- trailing_enabled: YES/NO
- trailing_start_pct
- trailing_distance_pct
- break_even_enabled: YES/NO
- break_even_trigger_pct

---

## 4️⃣ Order Execution

- order_type_entry: Limit by default (Market fallback запрещён, если spread/slippage выше лимитов)
- retry_policy:
  - max_attempts: 3
  - retry_delay_sec: 2–10 (конфиг)
- slippage limits:
  - max_slippage_entry_pct
  - max_slippage_exit_pct
- spread guard:
  - max_spread_pct (повторно проверяется перед выставлением/перестановкой)

---

#### Execution Failure Matrix (Mandatory)

1) Order Rejected
- отменить ордер
- retry <= 3
- если не удалось: SCANNING с penalty/cooldown

2) Partial Fill
- если fill_ratio < min_fill_ratio по истечении partial_fill_timeout:
  - отменить остаток
  - перейти в EXITING (закрыть исполненную часть, если риск/размер не приемлем)
- иначе:
  - продолжать добор по retry policy

3) Timeout / No Fill
- cancel -> retry
- по исчерпанию попыток -> cooldown

4) Slippage Spike / Spread Spike
- отменить текущую операцию
- cooldown
- при повторном срабатывании в одной сессии -> IDLE или Controlled Stop (policy)

5) Data Staleness / PriceBug
- stop new orders
- cancel active entry orders
- ERROR_HALT если не восстановлено

---

#### Observability & Audit Trail (Mandatory)

Events (минимальный список):
- mode_selected {SHOT|HOOK|STRIKE, timestamp, reason_summary}
- detector_fired {asset, depth, timeframe, rollback, volume, context}
- state_transition {from, to, reason}
- order_submitted {asset, side, type, qty, price_limit, attempt}
- order_modified {asset, new_price, reason}
- order_filled {asset, qty, avg_price, slippage, partial=true/false}
- order_cancelled {asset, reason}
- position_opened {asset, qty, avg_price}
- exit_started {reason: TP|SL|TIME|EMERGENCY}
- position_closed {asset, pnl, duration}
- cooldown_started / cooldown_ended {reason}
- error_halt {error_code, context}

Metrics (минимальный список):
- equity, strategy_pnl, pnl_daily
- trades_count, winrate, avg_trade_duration
- avg_slippage_entry/exit, rejection_rate, partial_fill_rate
- time_in_state (по каждому состоянию)
- detector_stats (fires, conversions to trades)

---

#### Stress Tests & Acceptance Criteria (Mandatory)

Сценарии рынка:
1) FLAT: минимальные входы, отсутствие «заморозки депозита» бесконечно (order age limit обязателен)
2) SAW: ограничение количества убыточных входов через cooldown
3) DUMP: быстрый SL/time-stop, отсутствие усреднений без лимита
4) FAKE PUMP / whipsaw: частичная фиксация + trailing/BE защищают результат

Сценарии исполнения:
5) Reject / API errors: attempts <= 3, затем cooldown
6) Partial fill: deterministic unwind или корректное доведение до min_fill_ratio
7) Slippage/spread spike: отмена + cooldown, без бесконечных повторов

Acceptance (hard):
- Нет нарушений инвариантов state machine
- Нет silent-fails
- SIM=OFF режим корректен (safe defaults)
- Все mandatory events/metrics присутствуют

---

#### SIM / REAL Split

**REAL (mandatory)**
- detector baseline (depth/timeframe/rollback)
- выбор режима по safe-default policy
- исполнение ордеров и риск-контуры
- работа при SIM = OFF

**SIM (optional)**
- расширенный scouting: подбор watchlist
- режим рынка и рекомендации по параметрам
- ScoutNotes (no commands)

---

### Origin (Non-Normative)

Inspired by MoonBot MoonShot / MoonHook / MoonStrike ideas.
Only high-level impulse concepts were used.
No parameters, execution logic, or architectural dependencies were adopted.

---

#### Status
Draft (v0.9)



==================================================3==================================================

### Strategy: Range Reversion (Flat/Channel)

#### Purpose
Торговля **диапазонного (FLAT) режима** через возврат цены к середине диапазона:
покупка вблизи нижней границы диапазона и фиксация прибыли в районе mid/upper-band.

Стратегия **не предназначена** для трендовых режимов и должна уметь “не торговать”.

---

#### Scope
- Type: Single-Asset (Mean Reversion / Range)
- Mode: REAL (обязателен SIM=OFF режим)
- Market: Spot by default (Futures optional later)
- Concurrency:
  - Default: max 1 active position одновременно
  - Watchlist может быть шире, но позиция — одна

---

#### Core Principle
- Торговать **только при подтверждённом диапазоне** (market_regime == FLAT).
- Если режим рынка сменился на non-FLAT — новые входы запрещены, позиция закрывается по правилам выхода.
- Усреднение **разрешено ограниченно** (bounded), без роста риска.

---

#### State Machine (Deterministic)

Состояния:
- IDLE: стратегия выключена или условия не позволяют сканировать рынок
- SCANNING: мониторинг watchlist, расчёт диапазона/режима
- ARMED: диапазон подтверждён, ожидается касание зоны входа
- ORDER_PLACED: выставлен entry buy-ордер
- PARTIALLY_FILLED: частичное исполнение entry
- POSITION_OPEN: позиция открыта и управляется
- EXITING: выполняются закрывающие ордера (TP/SL/time-stop/regime-change/emergency)
- CLOSED: позиция закрыта, цикл завершен
- ERROR_HALT: критическая ошибка исполнения/данных

Разрешённые переходы:
- IDLE -> SCANNING (разрешено торговать, нет глобальных блокировок)
- SCANNING -> ARMED (regime=FLAT + диапазон валиден)
- ARMED -> ORDER_PLACED (условия входа выполнены, выставлен ордер)
- ORDER_PLACED -> PARTIALLY_FILLED (partial fill)
- ORDER_PLACED -> POSITION_OPEN (fill complete)
- PARTIALLY_FILLED -> POSITION_OPEN (добор завершён) или -> EXITING (отмена остатка + unwind)
- POSITION_OPEN -> EXITING (TP/SL/TIME/REGIME_CHANGE/EMERGENCY)
- EXITING -> CLOSED
- * -> ERROR_HALT (критическая ошибка исполнения/данных)

Инварианты:
- В EXITING запрещены любые новые входы.
- При regime != FLAT запрещены новые входы (SCANNING может продолжаться).
- Любой silent-fail запрещён: все сбои фиксируются событиями + действиями.

---

#### Preconditions (Global Filters)

Стратегия **НЕ АКТИВНА**, если:
- SAFE MODE = ON
- глобальная торговля запрещена
- Equity Drawdown ≥ 20 %

**Liquidity / Volume**
- Min orderbook depth (top 1%): ≥ 50 000 USDT
- 24h Volume: ≥ 10 000 000 USDT

**Spread**
- Max spread: ≤ 0.30 %

**Asset Lists**
- Whitelist / Blacklist применимы (наследуется из общих правил бота)

---

## 1️⃣ Range Model (Диапазон)

Стратегия вычисляет диапазон на rolling-window:
- range_window_sec: окно расчёта диапазона
- range_high: максимум цены в окне
- range_low: минимум цены в окне
- range_mid: (range_high + range_low) / 2
- range_width_pct: (range_high - range_low) / range_mid

Диапазон считается валидным, если:
- range_width_pct ∈ [range_width_min_pct, range_width_max_pct]
- волатильность/шум ниже порога (volatility_cap)
- отсутствует трендовый уклон (trend_slope_cap)

---

## 2️⃣ Entry Rules (Вход)

**Зона входа (нижний бэнд):**
- entry_band_pct: доля ширины диапазона от range_low (например 10%)
- вход разрешён, если price <= range_low + entry_band_pct * (range_high - range_low)

**Подтверждения (минимум):**
- spread <= max_spread_pct
- нет импульсного режима (anti-impulse guard)
- regime == FLAT

**Entry Order**
- order_type_entry: Limit by default
- entry_price:
  - базово: near best_bid с поправкой (entry_limit_offset_pct)
  - запрещено ставить “внутри спреда”, если тик-сайз не позволяет

---

## 3️⃣ Position Sizing (Risk)

- order_size_mode: FIXED_NOTIONAL | PCT_EQUITY
- max_position_pct_of_equity: верхняя граница
- max_concurrent_positions: 1 (default)

Optional bounded add:
- max_adds: 1
- add_trigger_pct: дополнительный вход только при отклонении ниже entry на add_trigger_pct
- risk non-increasing invariant: суммарный риск позиции не должен расти

---

## 4️⃣ Position Management (Unified)

**Take Profit**
- tp_mid_enabled: YES/NO (фиксируем часть у range_mid)
- tp_mid_ratio: доля закрытия на mid
- tp_upper_enabled: YES/NO (фиксируем остаток у верхнего бэнда)
- tp_upper_band_pct: зона у range_high (например 5%)

**Stop Loss**
- hard_sl_pct: обязательный (ниже range_low)
- time_stop_sec: обязательный (если цена не вернулась к mid)
- strategy_max_loss_pct: лимит потерь стратегии (сессия/день)
- portfolio_emergency_sl: глобальный хук (если есть)

**Regime Change Exit**
- если regime != FLAT более regime_change_confirm_sec:
  - начать EXITING (controlled exit)

---

## 5️⃣ Order Execution

- retry_policy:
  - max_attempts: 3
  - retry_delay_sec: 2–10 (конфиг)
- slippage limits:
  - max_slippage_entry_pct
  - max_slippage_exit_pct
- spread guard:
  - max_spread_pct (проверяется перед выставлением/модификацией)

---

#### Execution Failure Matrix (Mandatory)

1) Order Rejected
- отменить ордер
- retry <= 3
- если не удалось: SCANNING с penalty/cooldown

2) Partial Fill
- если fill_ratio < min_fill_ratio по истечении partial_fill_timeout:
  - отменить остаток
  - перейти в EXITING (закрыть исполненную часть, если риск/размер не приемлем)
- иначе:
  - продолжать добор по retry policy

3) Timeout / No Fill
- cancel -> retry
- по исчерпанию попыток -> cooldown

4) Spread/Slippage Spike
- отменить текущую операцию
- cooldown
- при повторе в одной сессии -> IDLE или Controlled Stop (policy)

5) Data Staleness / PriceBug
- stop new orders
- cancel active orders
- ERROR_HALT если не восстановлено

---

#### Observability & Audit Trail (Mandatory)

Events (минимальный список):
- regime_changed {asset, old, new, reason_summary}
- range_computed {asset, window_sec, high, low, mid, width_pct}
- state_transition {from, to, reason}
- order_submitted / order_filled / order_cancelled {asset, ...}
- position_opened / exit_started / position_closed {asset, ...}
- cooldown_started / cooldown_ended {reason}
- error_halt {error_code, context}

Metrics (минимальный список):
- equity, strategy_pnl, pnl_daily
- trades_count, winrate, avg_trade_duration
- avg_range_width_pct, time_in_regime_flat
- avg_slippage_entry/exit, rejection_rate, partial_fill_rate
- time_in_state (по каждому состоянию)

---

#### Stress Tests & Acceptance Criteria (Mandatory)

Сценарии рынка:
1) FLAT: стратегия торгует; drawdown ограничен; нет частых входов
2) TREND: стратегия не открывает новые позиции; при смене режима закрывает открытые
3) SAW: после N убыточных попыток активируется cooldown
4) DUMP: hard SL/time-stop ограничивают убыток

Сценарии исполнения:
5) Reject / Partial / Timeout / Spread spike: deterministic handling, no silent fail

Acceptance (hard):
- Нет входов при regime != FLAT
- SIM=OFF режим корректен (safe defaults)
- Все mandatory events/metrics присутствуют

---

#### SIM / REAL Split

**REAL (mandatory)**
- baseline regime=FLAT проверка + расчёт диапазона
- вход/выход + риск-контуры
- работа при SIM = OFF

**SIM (optional)**
- улучшенная классификация режима, подбор watchlist
- рекомендации по параметрам (bounded)

---

#### Status
Draft (v0.3)


==================================================4==================================================

### Strategy: Trend Rider (Breakout + Filter)

#### Purpose
Торговля **трендового режима** через подтверждённый пробой/импульс и сопровождение позиции по trailing.
Цель — брать продолжение движения, ограничивая убытки через жёсткий риск-контур и отказ от “досиживания”.

---

#### Scope
- Type: Single-Asset (Trend Following)
- Mode: REAL (обязателен SIM=OFF режим)
- Market: Spot by default (Futures optional later)
- Concurrency:
  - Default: max 1 active position одновременно

---

#### Core Principle
- Вход допускается только при подтверждённом тренде (market_regime == TREND).
- Выход — в первую очередь по trailing (profit letting run), убыток ограничен hard SL.
- Стратегия должна “не торговать” в FLAT/SAW режимах.

---

#### State Machine (Deterministic)

Состояния:
- IDLE: стратегия выключена или условия не позволяют сканировать рынок
- SCANNING: мониторинг watchlist, оценка режима/триггеров
- ARMED: тренд подтверждён, ожидается trigger (breakout)
- ORDER_PLACED: выставлен entry-ордер
- PARTIALLY_FILLED: частичное исполнение entry
- POSITION_OPEN: позиция открыта и сопровождается
- EXITING: выполняются закрывающие ордера (trailing/SL/time-stop/emergency)
- CLOSED: позиция закрыта, цикл завершен
- ERROR_HALT: критическая ошибка исполнения/данных

Инварианты:
- В EXITING запрещены новые входы.
- При regime != TREND запрещены новые входы.
- Любой silent-fail запрещён: все сбои фиксируются событиями + действиями.

---

#### Preconditions (Global Filters)

Стратегия **НЕ АКТИВНА**, если:
- SAFE MODE = ON
- глобальная торговля запрещена
- Equity Drawdown ≥ 20 %

**Liquidity / Volume**
- Min orderbook depth (top 1%): ≥ 50 000 USDT
- 24h Volume: ≥ 10 000 000 USDT

**Spread**
- Max spread: ≤ 0.30 %

**Volatility Cap (Anti-Blowoff)**
- если intraday_volatility_pct > volatility_cap_pct:
  - вход запрещён (ожидание нормализации)

---

## 1️⃣ Trend Model (Режим TREND)

Минимальная baseline-проверка в REAL:
- fast_ma > slow_ma (как фильтр)
- slope/момендум выше порога
- не FLAT по диапазону (range_width_pct выше min)

Параметры:
- trend_fast_ma_period
- trend_slow_ma_period
- trend_slope_min
- volatility_cap_pct

---

## 2️⃣ Entry Rules (Вход)

**Trigger: Breakout**
- breakout_window_sec: окно для уровня пробоя
- breakout_high: максимум цены в окне
- вход при price >= breakout_high * (1 + breakout_confirm_pct)

**Entry Order**
- order_type_entry: Limit if possible
- если breakout требует Market:
  - разрешать только при spread <= max_spread_pct и slippage <= max_slippage_entry_pct

---

## 3️⃣ Position Sizing (Risk)

- order_size_mode: FIXED_NOTIONAL | PCT_EQUITY
- max_position_pct_of_equity: верхняя граница
- max_trades_per_session: лимит попыток входа
- cooldown_after_loss_sec: обязательный

---

## 4️⃣ Position Management (Unified)

**Stop Loss**
- hard_sl_pct: обязательный (относительно entry)
- time_stop_sec: обязательный (если нет продолжения)
- strategy_max_loss_pct: лимит потерь стратегии (сессия/день)

**Trailing (Primary Exit)**
- trailing_enabled: YES (по умолчанию)
- trailing_start_pct: включение трейлинга после +X%
- trailing_distance_pct: расстояние трейлинга
- break_even_enabled: YES/NO
- break_even_trigger_pct

**Optional Partial TP**
- tp_partial_enabled: YES/NO
- tp_partial_level_pct
- tp_partial_ratio

---

## 5️⃣ Order Execution

- retry_policy:
  - max_attempts: 3
  - retry_delay_sec: 2–10 (конфиг)
- slippage limits:
  - max_slippage_entry_pct
  - max_slippage_exit_pct
- spread guard:
  - max_spread_pct

---

#### Execution Failure Matrix (Mandatory)

1) Order Rejected
- отменить ордер
- retry <= 3
- если не удалось: SCANNING с penalty/cooldown

2) Partial Fill
- если fill_ratio < min_fill_ratio по истечении partial_fill_timeout:
  - отменить остаток
  - перейти в EXITING (закрыть исполненную часть, если риск/размер не приемлем)
- иначе:
  - продолжать добор по retry policy

3) Timeout / No Fill
- cancel -> retry
- по исчерпанию попыток -> cooldown

4) Slippage/Spread Spike
- отменить текущую операцию
- cooldown
- при повторе -> IDLE или Controlled Stop (policy)

5) Data Staleness / PriceBug
- stop new orders
- cancel active orders
- ERROR_HALT если не восстановлено

---

#### Observability & Audit Trail (Mandatory)

Events (минимальный список):
- regime_changed {asset, old, new, reason_summary}
- breakout_triggered {asset, window_sec, breakout_high, confirm_pct}
- state_transition {from, to, reason}
- order_submitted / order_filled / order_cancelled {asset, ...}
- trailing_updated {asset, peak_price, stop_price}
- exit_started / position_closed {reason: TRAILING|SL|TIME|EMERGENCY}
- cooldown_started / cooldown_ended {reason}
- error_halt {error_code, context}

Metrics (минимальный список):
- equity, strategy_pnl, pnl_daily
- trades_count, winrate, avg_trade_duration
- avg_slippage_entry/exit, rejection_rate, partial_fill_rate
- time_in_state (по каждому состоянию)
- trend_time_in_regime, false_breakout_rate (derived)

---

#### Stress Tests & Acceptance Criteria (Mandatory)

Сценарии рынка:
1) TREND: стратегия открывает позиции и сопровождает trailing
2) FLAT: стратегия не открывает позиции (или очень редко при ошибке режима)
3) SAW/whipsaw: ограниченные убытки через cooldown + time-stop
4) DUMP: hard SL ограничивает убыток, нет повторных входов

Сценарии исполнения:
5) Reject / Partial / Timeout / Slippage spike: deterministic handling, no silent fail

Acceptance (hard):
- Нет входов при regime != TREND
- SIM=OFF режим корректен (safe defaults)
- Все mandatory events/metrics присутствуют

---

#### SIM / REAL Split

**REAL (mandatory)**
- baseline regime=TREND проверка + trigger breakout
- вход/выход + риск-контуры
- работа при SIM = OFF

**SIM (optional)**
- улучшенная классификация режима, подбор watchlist
- рекомендации по параметрам (bounded)

---

#### Status
Draft (v0.2)



==================================================5==================================================

### Strategy: Momentum Breakout (Pump Rider)

#### Purpose
Торговля **продолжения импульсного движения вверх** после подтверждённого пробоя (breakout),
при этом стратегия обязана защищаться от сценария **blow-off top** (кульминация → резкий разворот).

Важно: стратегия **не** реализует наивную логику “детект пампа → купить сразу”.
Стратегия торгует **пробой + продолжение**, с жёстким риск-контуром.

---

#### Scope
- Type: Single-Asset (Momentum / Trend Continuation)
- Mode: REAL (обязателен SIM=OFF режим)
- Market: Spot by default (Futures optional later)
- Concurrency:
  - Default: max 1 active position одновременно
  - Запрещены параллельные входы в разные активы в рамках одного цикла

---

#### Core Principle
- Вход разрешён только при подтверждённом режиме **TREND** (market_regime == TREND).
- При признаках кульминации (volatility/spread spike) вход запрещён.
- Основной выход — trailing (дать прибыли течь), убыток ограничен hard SL и time-stop.
- Стратегия должна “не торговать” в FLAT/SAW режимах.

---

#### State Machine (Deterministic)

Состояния:
- IDLE: стратегия выключена или условия не позволяют сканировать рынок
- SCANNING: мониторинг watchlist, оценка режима, поиск breakout-сетапов
- ARMED: режим TREND подтверждён, breakout-level рассчитан, ожидается подтверждение
- ORDER_PLACED: выставлен entry-ордер (stop-limit/limit)
- PARTIALLY_FILLED: частичное исполнение entry
- POSITION_OPEN: позиция открыта и сопровождается
- EXITING: выполняются закрывающие ордера (trailing/SL/time-stop/emergency)
- CLOSED: позиция закрыта, цикл завершён
- COOLDOWN: охлаждение после лосса/серии попыток
- ERROR_HALT: критическая ошибка исполнения/данных

Разрешённые переходы:
- IDLE -> SCANNING
- SCANNING -> ARMED (regime=TREND + breakout_level валиден + фильтры пройдены)
- ARMED -> ORDER_PLACED (breakout_confirmed)
- ORDER_PLACED -> PARTIALLY_FILLED
- ORDER_PLACED -> POSITION_OPEN
- PARTIALLY_FILLED -> POSITION_OPEN или -> EXITING (cancel remainder + unwind)
- POSITION_OPEN -> EXITING (TRAILING|SL|TIME|EMERGENCY)
- EXITING -> CLOSED
- CLOSED -> COOLDOWN (по policy) или -> SCANNING
- * -> ERROR_HALT

Инварианты:
- В EXITING запрещены новые входы.
- При regime != TREND запрещены новые входы.
- Anti-blowoff guard: при spread/volatility spike вход запрещён (даже если breakout произошёл).
- Любой silent-fail запрещён: все сбои фиксируются событиями + действиями.

---

#### Preconditions (Global Filters)

Стратегия **НЕ АКТИВНА**, если:
- SAFE MODE = ON
- глобальная торговля запрещена
- Equity Drawdown ≥ 20 %

**Liquidity / Volume**
- Min orderbook depth (top 1%): ≥ 50 000 USDT
- 24h Volume: ≥ 10 000 000 USDT

**Spread**
- Max spread: ≤ 0.30 %

**Anti-Blowoff (mandatory)**
Вход запрещён, если выполняется хотя бы одно:
- spread > blowoff_max_spread_pct
- intraday_volatility_pct > blowoff_volatility_cap_pct
- pump_speed_pct_per_min > blowoff_speed_cap (опционально)

---

## 1️⃣ Trend + Breakout Model (Режим и уровень пробоя)

Параметры:
- trend_fast_ma_period
- trend_slow_ma_period
- trend_slope_min
- breakout_window_sec
- breakout_confirm_pct

Расчёт:
- breakout_high = max(price, breakout_window_sec)
- breakout_confirmed, если price >= breakout_high * (1 + breakout_confirm_pct)
- regime=TREND подтверждается baseline-фильтрами (MA + slope + non-FLAT)

---

## 2️⃣ Entry Rules (Вход)

**Entry Type (по умолчанию)**
- entry_order_type: STOP_LIMIT (если биржа поддерживает), иначе LIMIT с подтверждением
- entry_limit_offset_pct: лимит чуть ниже текущей цены, чтобы не ловить экстремальный проскальзывание
- entry_expiry_sec: если ордер не исполнен за время — отменить и вернуться в SCANNING

**Guards (обязательные перед выставлением)**
- spread <= max_spread_pct
- slippage_estimate <= max_slippage_entry_pct
- anti-blowoff условия НЕ активны
- regime == TREND

---

## 3️⃣ Position Sizing (Risk)

- order_size_mode: FIXED_NOTIONAL | PCT_EQUITY
- max_position_pct_of_equity: верхняя граница
- max_trades_per_session: лимит попыток входа
- cooldown_after_loss_sec: обязательный
- max_failed_entries_per_session: ограничение на серии отмен/неисполнений

---

## 4️⃣ Position Management (Unified)

**Stop Loss**
- hard_sl_pct: обязательный
- time_stop_sec: обязательный (если продолжения нет)
- strategy_max_loss_pct: лимит потерь стратегии (сессия/день)

**Trailing (Primary Exit)**
- trailing_enabled: YES (по умолчанию)
- trailing_start_pct: включение trailing после +X%
- trailing_distance_pct: расстояние trailing
- trailing_update_min_interval_ms: минимальный интервал обновления

**Break-even (optional)**
- break_even_enabled: YES/NO
- break_even_trigger_pct

**Optional Partial TP**
- tp_partial_enabled: YES/NO
- tp_partial_level_pct
- tp_partial_ratio

---

## 5️⃣ Exit Rules (Выход)

Триггеры выхода:
- TRAILING: цена пересекла trailing stop
- SL: цена пересекла hard SL
- TIME: истёк time_stop_sec без достижения условий продолжения
- EMERGENCY: глобальный риск-хук / portfolio emergency

---

## 6️⃣ Order Execution

- retry_policy:
  - max_attempts: 3
  - retry_delay_sec: 2–10 (конфиг)
- slippage limits:
  - max_slippage_entry_pct
  - max_slippage_exit_pct
- spread guard:
  - max_spread_pct (проверяется перед выставлением/модификацией)

---

#### Execution Failure Matrix (Mandatory)

1) Order Rejected
- отменить ордер
- retry <= 3
- если не удалось: COOLDOWN

2) Partial Fill
- если fill_ratio < min_fill_ratio по истечении partial_fill_timeout:
  - отменить остаток
  - перейти в EXITING (закрыть исполненную часть, если риск/размер не приемлем)
- иначе:
  - продолжать добор по retry policy

3) Timeout / No Fill
- cancel -> retry
- по исчерпанию попыток -> COOLDOWN

4) Spread/Slippage Spike (во время входа)
- отменить entry
- COOLDOWN
- при повторе -> IDLE или Controlled Stop (policy)

5) Data Staleness / PriceBug
- stop new orders
- cancel active orders
- ERROR_HALT если не восстановлено

---

#### Observability & Audit Trail (Mandatory)

Events (минимальный список):
- regime_changed {asset, old, new, reason_summary}
- breakout_level_computed {asset, window_sec, breakout_high}
- breakout_confirmed {asset, confirm_pct, price}
- anti_blowoff_blocked {asset, reason, spread, volatility, speed}
- state_transition {from, to, reason}
- order_submitted / order_filled / order_cancelled {asset, ...}
- trailing_updated {asset, peak_price, stop_price}
- exit_started / position_closed {reason: TRAILING|SL|TIME|EMERGENCY}
- cooldown_started / cooldown_ended {reason}
- error_halt {error_code, context}

Metrics (минимальный список):
- equity, strategy_pnl, pnl_daily
- trades_count, winrate, avg_trade_duration
- avg_slippage_entry/exit, rejection_rate, partial_fill_rate
- time_in_state (по каждому состоянию)
- false_breakout_rate (derived)
- anti_blowoff_blocks_count

---

#### Stress Tests & Acceptance Criteria (Mandatory)

Сценарии рынка:
1) TREND: стратегия открывает позицию и сопровождает trailing
2) FLAT: стратегия не входит
3) SAW/whipsaw: ограниченные убытки через cooldown + time-stop
4) BLOWOFF TOP: вход блокируется anti-blowoff guard или позиция быстро выходит по trailing/SL
5) DUMP: hard SL ограничивает убыток, повторные входы ограничены

Сценарии исполнения:
6) Reject / Partial / Timeout / Slippage spike: deterministic handling, no silent fail

Acceptance (hard):
- Нет входов при regime != TREND
- Нет входов при anti-blowoff активном
- SIM=OFF режим корректен (safe defaults)
- Все mandatory events/metrics присутствуют

---

#### SIM / REAL Split

**REAL (mandatory)**
- baseline regime=TREND + breakout модель
- anti-blowoff guards
- исполнение входа/выхода + риск-контуры
- работа при SIM = OFF

**SIM (optional)**
- улучшенная классификация режима, подбор watchlist
- рекомендации по параметрам (bounded)

---

#### Status
Draft (v0.2)

==================================================6==================================================

### Strategy: Spread Scalper (Trade-Zone Spread)

#### Purpose
Торговля **краткосрочной “пилы”**: активные сделки в узкой зоне времени и цены (trade-zone),
где цена многократно колеблется вверх/вниз, а спред — это **размах цены**
на коротком интервале при высокой плотности трейдов.

Цель: поставить лимитный вход **внутри** зоны колебаний и закрыться ближе к верхней части зоны,
пока рынок остаётся **без импульса**.

---

#### Scope
- Type: Single-Asset (Microstructure / Range Scalping)
- Mode: REAL (обязателен SIM=OFF режим)
- Market: Spot by default
- Concurrency:
  - Default: max 1 active position одновременно
  - Никаких “пачек” ордеров и сеток

---

#### Core Principle
- Стратегия торгует **только** при подтверждённой зоне:
  - высокая плотность трейдов
  - размах цены присутствует **на каждом сегменте окна**
  - рынок не в импульсе и не в тренде (anti-impulse + regime gate)
- Если рынок “проснулся” (импульс/волатильность/спред/объём) — стратегия **немедленно выходит**.
- Усреднение запрещено. Повторные входы строго ограничены.

---

#### State Machine (Deterministic)

Состояния:
- IDLE: стратегия выключена или условия не позволяют сканировать рынок
- SCANNING: мониторинг, расчёт trade-zone метрик
- ARMED: зона подтверждена, рассчитаны границы min/max и уровни входа/выхода
- ORDER_PLACED: выставлен entry buy-ордер
- PARTIALLY_FILLED: частичное исполнение entry
- POSITION_OPEN: позиция открыта и управляется
- EXITING: выполняются закрывающие ордера (TP/SL/time-stop/impulse-exit)
- COOLDOWN: охлаждение после сделки/срыва условий
- CLOSED: цикл завершён
- ERROR_HALT: критическая ошибка исполнения/данных

Инварианты:
- В EXITING запрещены новые входы.
- Нет входов при market_regime != FLAT (или при anti-impulse guard активном).
- Любой silent-fail запрещён: все сбои фиксируются событиями + действиями.
- Max 1 позиция, max 1 active entry order.

---

#### Preconditions (Global Filters)

Стратегия **НЕ АКТИВНА**, если:
- SAFE MODE = ON
- глобальная торговля запрещена
- Equity Drawdown ≥ 20 %

**Liquidity / Volume**
- Min orderbook depth (top 1%): ≥ 50 000 USDT
- 24h Volume: ≥ 10 000 000 USDT

**Spread (bid/ask guard)**
- max_spread_pct ≤ 0.30 % (проверяется перед входом и перед выходом)

---

## 1️⃣ Trade-Zone Detector (Адаптация MoonBot Spread)

Ниже — “перевод” MoonBot параметров в наши термины.
Мы сохраняем смысл, но убираем лишнее и добавляем risk-ограничители.

### Окно анализа
- tz_time_interval_sec 
  Ширина зоны по времени, на которой считается детект (мин. 1 сек).

### Плотность трейдов (trade activity)
- tz_bin_ms = 200 (фиксировано как базовый бин; можно сделать параметром)
- tz_trades_density_pct  
  Доля бинов, где есть “живые” трейды (минимум 2 трейда с разной ценой) относительно окна.
- tz_trades_density_prev_pct 
  Плотность на предыдущем окне. Используется как фильтр “монета уже была живой/лежала”.
  Policy: для “пилы” обычно хотим НЕ полностью лежачие монеты, но и не импульс.
- tz_trades_count_min_per_bin  
  Жёсткий фильтр по числу трейдов в каждом бине (сильно зажимает, optional).

### Размах цены по сегментам
- tz_price_intervals 
  Делим окно на N отрезков, на каждом считаем min/max.
- tz_price_interval_shift  
  Фильтр против “единичных стрел” (anti-single-spike).
- tz_price_spread_min_pct 
  Детект считается валидным, если **на каждом сегменте** размах ≥ tz_price_spread_min_pct.

### Где именно внутри зоны ставить вход/выход
Сначала вычисляем границы зоны (на всём окне или на последних сегментах):
- tz_intervals_for_zone_calc 
  Сколько последних сегментов брать для min/max (0 = всё окно).

Затем задаём уровни:
- tz_entry_level_pct 
  Где ставить вход относительно min..max зоны (лонг: от min вверх).
- tz_exit_level_pct  
  Где ставить выход относительно min..max зоны.
  Policy: выход берётся как max(стратегический выход, tz_exit_level_pct), чтобы не занижать тейк.

### Ограничение размера входа по “микрообъёму” (защита от тонких рынков)
- entry_microvolume_reduce_ms   
  Ограничиваем размер entry ордера средним объёмом за маленький интервал.
- entry_min_notional 
  Если после редукции размер ниже — вход запрещён.

### Повторы входов (мы ограничиваем)
- repeat_if_profit_pct   
  В MoonBot это может разгонять активность. У нас:
  - repeat_max = 1 (по умолчанию)
  - repeat_window_sec = 1
  - repeat_if_profit_pct > 0 включает повтор только при **явном приближении к выходу**
  - любые повторы подчиняются cooldown и max_trades_per_session

---

## 2️⃣ Anti-Impulse & Regime Gate (обязательные улучшения)

- market_regime_required: FLAT
- anti_impulse_return_pct
- anti_impulse_volume_spike_mult
- anti_impulse_spread_spike_pct (bid/ask)
- data_latency_cap_ms (если доступно)
- stale_quotes_guard_sec

Если любой guard активен:
- вход запрещён
- если позиция уже есть → начать EXITING (impulse-exit)

---

## 3️⃣ Entry Rules (Вход)

Условия входа:
1) Detected trade-zone:
- tz_trades_density_pct ≥ tz_trades_density_min_pct
- (optional) tz_trades_density_prev_pct ≥ tz_trades_density_prev_min_pct
- tz_price_spread_min_pct ≥ configured threshold
- размах ≥ порога **на каждом сегменте**
2) Regime/anti-impulse:
- market_regime == FLAT
- anti-impulse guards = OK
3) Execution guards:
- spread <= max_spread_pct
- slippage_estimate <= max_slippage_entry_pct

Entry Order:
- order_type_entry: Limit
- entry_price = zone_min + tz_entry_level_pct/100 * (zone_max - zone_min)
- entry_expiry_sec: отменить, если не исполнился за время

---

## 4️⃣ Exit Rules (Выход)

Триггеры выхода:
- TP_ZONE: цена достигла уровня выхода внутри зоны  
  exit_price = zone_min + tz_exit_level_pct/100 * (zone_max - zone_min)
- TIME: истёк time_stop_sec (обязательный, короткий)
- SL: hard_sl_pct (обязательный)
- IMPULSE_EXIT: сработал любой anti-impulse guard
- EMERGENCY: глобальный риск-хук

---

## 5️⃣ Position Sizing (Risk)

- order_size_mode: FIXED_NOTIONAL | PCT_EQUITY
- max_position_pct_of_equity: низкий по умолчанию
- no averaging: max_adds = 0
- max_trades_per_session: ограничение попыток
- cooldown_after_trade_sec: обязательный

---

## 6️⃣ Order Execution

- Limit only
- retry_policy:
  - max_attempts: 2–3 (конфиг)
  - retry_delay_sec: 2–10
- slippage limits:
  - max_slippage_entry_pct
  - max_slippage_exit_pct
- spread guard:
  - max_spread_pct

---

#### Execution Failure Matrix (Mandatory)

1) Order Rejected
- отменить ордер
- retry <= max_attempts
- если не удалось: COOLDOWN

2) Partial Fill
- отменить остаток
- перейти в EXITING (закрыть исполненную часть по правилам)

3) Timeout / No Fill
- cancel -> COOLDOWN

4) Impulse/Volatility/Spread Spike
- немедленно EXITING
- COOLDOWN

5) Data Staleness / PriceBug
- cancel active orders
- ERROR_HALT если не восстановлено

---

#### Observability & Audit Trail (Mandatory)

Events (минимальный список):
- trade_zone_detected {asset, interval_sec, density_pct, spread_pct, segments_ok}
- zone_bounds_computed {asset, zone_min, zone_max, method}
- entry_level_set {asset, entry_level_pct, entry_price}
- exit_level_set {asset, exit_level_pct, exit_price}
- impulse_exit_triggered {asset, reason}
- repeat_entry_attempted {asset, reason}
- state_transition {from, to, reason}
- order_submitted / order_filled / order_cancelled {asset, ...}
- position_opened / exit_started / position_closed {asset, pnl, duration}
- cooldown_started / cooldown_ended {reason}
- error_halt {error_code, context}

Metrics (минимальный список):
- trades_count, winrate, avg_trade_duration
- avg_zone_width_pct, avg_density_pct
- impulse_exit_rate
- avg_slippage_entry/exit, rejection_rate, partial_fill_rate
- time_in_state (по каждому состоянию)

---

#### Stress Tests & Acceptance Criteria (Mandatory)

Сценарии рынка:
1) FLAT “пила”: стратегия входит редко, берёт короткие движения, time-stop работает
2) TREND: стратегия не входит (regime gate)
3) SAW/whipsaw: ограничение попыток + cooldown предотвращают пиление депозита
4) IMPULSE: мгновенный выход по impulse-exit, без усреднений

Сценарии исполнения:
5) Reject / Partial / Timeout: deterministic handling, no silent fail
6) Latency: при превышении data_latency_cap_ms вход блокируется

Acceptance (hard):
- Нет входов при anti-impulse guard активном
- Нет усреднений
- Нет бесконечных повторов
- SIM=OFF режим корректен (safe defaults)
- Все mandatory events/metrics присутствуют

---

#### SIM / REAL Split

**REAL (mandatory)**
- trade-zone detector (density + segment spread)
- guards (regime + anti-impulse + latency)
- вход/выход + риск-контуры
- работа при SIM = OFF

**SIM (optional)**
- статистика зон по активам (подбор watchlist)
- рекомендации параметров в диапазонах (bounded)

---

#### Status
Draft (v0.2)


==================================================7==================================================

### Strategy #7: Liquidity Sweep Fade (Stop-Hunt Reversal)

#### Purpose
Отработка **ложных пробоев**, вызванных краткосрочным выносом стоп-ордеров (*liquidity sweep*),  
с входом **только после завершения импульса** и подтверждённого возврата цены внутрь диапазона.

Стратегия **НЕ ловит импульс** и **НЕ торгует ножи**.  
Она торгует **исчерпание агрессии**.

---

#### Market Regime
- **PRIMARY:** POST-IMPULSE / RANGE  
- **FORBIDDEN:** CONFIRMED TREND, HIGH MOMENTUM
---

#### Regime & Signal Sources (Canonical)

- `market_regime` — **ТОЛЬКО из Orchestrator**
- `trend / range / session` — **ТОЛЬКО из Orchestrator**
- `impulse / volatility spike` — **ТОЛЬКО через ImpulseGuard / VolatilityGuard**
- стратегия **НЕ определяет режим рынка самостоятельно**

---

#### Preconditions (Hard)
Вход **запрещён**, если:
- `market_regime == TREND`
- активен `ImpulseGuard`
- bid/ask spread > `max_spread_pct`
- ликвидность ниже `min_depth`
- активен `LatencyGuard`
- активен SAFE или PANIC режим

---

#### Detection Logic (Liquidity Sweep)

*Sweep* считается валидным, если **все условия выполнены**:
- цена пробила локальный high/low (уровень)
- пробой сопровождался всплеском объёма и скорости
- движение длилось ограниченное время
- после экстремума:
  - скорость падает
  - объём снижается
  - отсутствует продолжение

Фиксируются параметры:
- `sweep_high / sweep_low`
- `sweep_depth_pct`
- `sweep_duration_sec`

---

#### Entry Logic (Fade, NOT Catch)

Вход **только после подтверждения завершения импульса**:
- цена вернулась **внутрь** диапазона до *sweep*
- отсутствует повторное ускорение
- подтверждена стабилизация (N тиков без новых экстремумов)

**Entry:**
- **type:** `LIMIT`
- **direction:**
  - sweep вверх → `SHORT`
  - sweep вниз → `LONG`
- **entry_price:**
  - внутри диапазона возврата
  - не ближе X% к экстремуму sweep

---

#### Exit Logic

**Take Profit**
- основной: возврат к локальному балансу / VWAP / midpoint диапазона
- допускается частичное закрытие

**Stop Loss**
- обязательный `hard SL`
- за экстремумом sweep + buffer

**Time Stop**
- если цена не двигается в нужную сторону в течение `time_stop_sec` → `EXIT`

**Emergency Exit**
- повторное ускорение в сторону sweep
- срабатывание `ImpulseGuard`

---

#### State Machine

**States:**
- `IDLE`
- `SCANNING`
- `SWEEP_DETECTED`
- `WAIT_CONFIRMATION`
- `ENTERING`
- `ACTIVE`
- `EXITING`
- `COOLDOWN`
- `CLOSED`
- `ERROR_HALT`

**Invariants:**
- вход запрещён в `WAIT_CONFIRMATION`
- в `EXITING` запрещены новые ордера
- максимум **1 позиция**
- максимум **1 попытка на один sweep**

---

#### Risk & Limits
- `max_position_pct_of_equity`: **LOW**
- `max_trades_per_session`: ограничено
- усреднение **запрещено**
- `cooldown_after_trade_sec`: обязателен

---

#### Execution Rules
- entry: `LIMIT` only
- retries: ограничены
- partial fill:
  - остаток отменяется
  - исполненная часть управляется стандартно
- `SlippageGuard` обязателен

---

#### Execution Failure Matrix
- **Reject** → retry → `COOLDOWN`
- **Partial fill** → cancel remainder → manage position
- **Timeout** → cancel → `COOLDOWN`
- **Data staleness** → cancel all → `ERROR_HALT`
- **Impulse during position** → emergency `EXIT`

---

#### Observability

**Events**
- `sweep_detected`
- `sweep_confirmed`
- `entry_submitted`
- `entry_filled`
- `impulse_exit_triggered`
- `stop_loss_hit`
- `time_stop_exit`
- `state_transition`
- `cooldown_started`

**Metrics**
- `sweeps_detected`
- `entry_rate`
- `winrate`
- `avg_trade_duration`
- `avg_drawdown_per_trade`
- `impulse_exit_rate`

---

#### SIM / REAL Split

**REAL**
- полный детект и исполнение
- корректная работа при `SIM = OFF`

**SIM (optional)**
- анализ качества sweep-детекта
- подбор параметров в допустимых диапазонах

---

#### Status
**Draft → Candidate**

==================================================8==================================================

### Strategy #8: Failed Breakout Reversion (False Trend Killer)

#### Purpose
Отработка **провалившихся пробоев**, когда рынок пытается перейти в тренд,
но **не получает подтверждения** и возвращается обратно в диапазон.

Стратегия торгует **момент признания ошибки рынком**,  
а не сам пробой.

---

#### Market Regime
- **PRIMARY:** FLAT → FAILED_TREND  
- **FORBIDDEN:** CONFIRMED TREND, HIGH MOMENTUM
---

#### Regime & Signal Sources (Canonical)

- `market_regime` — **ТОЛЬКО из Orchestrator**
- `trend / range / session` — **ТОЛЬКО из Orchestrator**
- `impulse / volatility spike` — **ТОЛЬКО через ImpulseGuard / VolatilityGuard**
- стратегия **НЕ определяет режим рынка самостоятельно**

---

#### Preconditions (Hard)
Вход **запрещён**, если:
- `market_regime == TREND`
- активен `ImpulseGuard`
- bid/ask spread > `max_spread_pct`
- ликвидность ниже `min_depth`
- активен `LatencyGuard`
- активен SAFE или PANIC режим

---

#### Detection Logic (Failed Breakout)

Пробой считается **провалившимся**, если:
- цена вышла за границу диапазона / уровня
- отсутствует подтверждение объёмом и скоростью
- импульс быстро затухает
- цена возвращается **обратно под уровень пробоя**

Фиксируются параметры:
- `breakout_level`
- `breakout_depth_pct`
- `breakout_duration_sec`
- `failed_confirmation_window_sec`

---

#### Entry Logic (Reversion after Failure)

Вход **только после подтверждения провала пробоя**:
- цена закрылась обратно **внутри** диапазона
- отсутствует повторное ускорение в сторону пробоя
- подтверждена стабилизация (N тиков без новых экстремумов)

**Entry:**
- **type:** `LIMIT`
- **direction:**
  - ложный пробой вверх → `SHORT`
  - ложный пробой вниз → `LONG`
- **entry_price:**
  - сразу за уровнем возврата
  - не ближе X% к уровню повторного пробоя

---

#### Exit Logic

**Take Profit**
- основной: центр диапазона / VWAP
- допускается частичное закрытие

**Stop Loss**
- обязательный `hard SL`
- за уровнем пробоя + buffer

**Time Stop**
- если возврат не развивается в течение `time_stop_sec` → `EXIT`

**Emergency Exit**
- повторный импульс в сторону пробоя
- повторный выход цены за уровень
- срабатывание `ImpulseGuard`

---

#### State Machine

**States:**
- `IDLE`
- `SCANNING`
- `BREAKOUT_DETECTED`
- `FAILURE_CONFIRMED`
- `ENTERING`
- `ACTIVE`
- `EXITING`
- `COOLDOWN`
- `CLOSED`
- `ERROR_HALT`

**Invariants:**
- вход запрещён до `FAILURE_CONFIRMED`
- в `EXITING` запрещены новые ордера
- максимум **1 позиция**
- максимум **1 вход на один пробой**

---

#### Risk & Limits
- `max_position_pct_of_equity`: **LOW**
- `max_trades_per_session`: ограничено
- усреднение **запрещено**
- `cooldown_after_trade_sec`: обязателен

---

#### Execution Rules
- entry: `LIMIT` only
- retries: ограничены
- partial fill:
  - остаток отменяется
  - исполненная часть управляется стандартно
- `SlippageGuard` обязателен

---

#### Execution Failure Matrix
- **Reject** → retry → `COOLDOWN`
- **Partial fill** → cancel remainder → manage position
- **Timeout** → cancel → `COOLDOWN`
- **Data staleness** → cancel all → `ERROR_HALT`
- **Impulse during position** → emergency `EXIT`

---

#### Observability

**Events**
- `breakout_detected`
- `failure_confirmed`
- `entry_submitted`
- `entry_filled`
- `false_breakout_exit`
- `stop_loss_hit`
- `time_stop_exit`
- `state_transition`
- `cooldown_started`

**Metrics**
- `false_breakouts_detected`
- `entry_rate`
- `winrate`
- `avg_trade_duration`
- `avg_drawdown_per_trade`
- `false_breakout_failure_rate`

---

#### SIM / REAL Split

**REAL**
- полный детект, подтверждение провала и исполнение
- корректная работа при `SIM = OFF`

**SIM (optional)**
- анализ частоты ложных пробоев
- подбор параметров подтверждения в допустимых диапазонах

---

#### Status
**Draft → Candidate**

==================================================9==================================================

### Strategy #9: Session Open Range Play

#### Purpose
Отработка **статистического поведения цены в момент открытия торговой сессии**,
когда ликвидность и волатильность резко меняются, формируя предсказуемый initial range.

Стратегия торгует **первые минуты сессии** и **НЕ активна вне заданного временного окна**.

---

#### Market Regime
- **PRIMARY:** SESSION_OPEN / EARLY_RANGE  
- **FORBIDDEN:** MID-SESSION, LOW LIQUIDITY, PANIC
---

#### Regime & Signal Sources (Canonical)

- `market_regime` — **ТОЛЬКО из Orchestrator**
- `trend / range / session` — **ТОЛЬКО из Orchestrator**
- `impulse / volatility spike` — **ТОЛЬКО через ImpulseGuard / VolatilityGuard**
- стратегия **НЕ определяет режим рынка самостоятельно**

---

#### Preconditions (Hard)
Вход **запрещён**, если:
- текущее время вне окна `session_open_window`
- активен `LatencyGuard`
- bid/ask spread > `max_spread_pct`
- ликвидность ниже `min_depth`
- активен SAFE или PANIC режим

---

#### Detection Logic (Initial Range)

Initial Range формируется, если:
- наступило время открытия заданной сессии
- в течение `initial_range_minutes`:
  - цена колеблется внутри ограниченного диапазона
  - присутствует достаточная торговая активность
- диапазон зафиксирован и **больше не расширяется**

Фиксируются параметры:
- `session_open_time`
- `initial_range_high`
- `initial_range_low`
- `initial_range_size_pct`

---

#### Entry Logic (Mode-Dependent)

Стратегия работает в **одном из режимов**, заданном параметром `entry_mode`.

**Mode: BREAKOUT**
- вход при выходе цены за границу initial range
- подтверждение: импульс + объём
- направление:
  - пробой вверх → `LONG`
  - пробой вниз → `SHORT`

**Mode: REVERSION**
- вход при ложном выходе за границу range
- возврат цены внутрь диапазона
- направление:
  - ложный выход вверх → `SHORT`
  - ложный выход вниз → `LONG`

**Entry:**
- **type:** `LIMIT` (по умолчанию)
- **entry_price:**
  - рядом с границей range (breakout)
  - либо внутри диапазона (reversion)

---

#### Exit Logic

**Take Profit**
- BREAKOUT:
  - фиксированное расширение range
  - либо trailing stop
- REVERSION:
  - midpoint range
  - либо VWAP сессии

**Stop Loss**
- обязательный `hard SL`
- за противоположной границей range + buffer

**Time Stop**
- закрытие позиции при выходе за пределы `session_trade_window`

**Emergency Exit**
- резкое падение ликвидности
- всплеск волатильности вне ожидаемого сценария
- срабатывание `ImpulseGuard`

---

#### State Machine

**States:**
- `IDLE`
- `WAIT_SESSION_OPEN`
- `FORMING_RANGE`
- `RANGE_FIXED`
- `ENTERING`
- `ACTIVE`
- `EXITING`
- `SESSION_END`
- `CLOSED`
- `ERROR_HALT`

**Invariants:**
- торговля разрешена **только в окне сессии**
- не более **1 сделки на сессию**
- при `SESSION_END` → принудительный `EXIT`

---

#### Risk & Limits
- `max_position_pct_of_equity`: **LOW**
- `max_trades_per_session`: **1**
- усреднение **запрещено**
- `cooldown_after_session`: обязателен

---

#### Execution Rules
- entry: `LIMIT` preferred, `MARKET` запрещён по умолчанию
- retries: минимальные
- partial fill:
  - остаток отменяется
  - исполненная часть управляется стандартно
- `SlippageGuard` обязателен

---

#### Execution Failure Matrix
- **Reject** → отмена попытки → `SESSION_END`
- **Partial fill** → cancel remainder → manage position
- **Timeout** → cancel → `SESSION_END`
- **Data staleness** → cancel all → `ERROR_HALT`
- **Impulse anomaly** → emergency `EXIT`

---

#### Observability

**Events**
- `session_open_detected`
- `initial_range_formed`
- `range_fixed`
- `entry_submitted`
- `entry_filled`
- `session_exit`
- `stop_loss_hit`
- `time_stop_exit`
- `state_transition`

**Metrics**
- `sessions_traded`
- `range_size_avg`
- `winrate`
- `avg_trade_duration`
- `avg_slippage`
- `session_pnl`

---

#### SIM / REAL Split

**REAL**
- вся логика тайминга, range и исполнения
- корректная работа при `SIM = OFF`

**SIM (optional)**
- анализ статистики range по сессиям
- подбор параметров `initial_range_minutes` и `entry_mode`

---

#### Status
**Draft → Candidate**

==================================================10==================================================

### Strategy #10: Trend Pullback Continuation

#### Purpose
Продолжение **уже подтверждённого тренда** через входы на контролируемых откатах
после импульсных движений.

Стратегия **НЕ ищет развороты** и **НЕ торгует флэт**.  
Она торгует **возобновление движения по тренду**.

---

#### Market Regime
- **PRIMARY:** TREND  
- **FORBIDDEN:** FLAT, RANGE, POST-IMPULSE FADE
---

#### Regime & Signal Sources (Canonical)

- `market_regime` — определяется **ТОЛЬКО Orchestrator**
- `trend / flat / session` — **ТОЛЬКО Orchestrator**
- `impulse / volatility spike` — **ТОЛЬКО через VolatilityGuard / ImpulseGuard**
- стратегия **НЕ вычисляет режим рынка самостоятельно**

---

#### Regime & Signal Sources (Canonical)

- `market_regime` — **ТОЛЬКО из Orchestrator**
- `trend / range / session` — **ТОЛЬКО из Orchestrator**
- `impulse / volatility spike` — **ТОЛЬКО через ImpulseGuard / VolatilityGuard**
- стратегия **НЕ определяет режим рынка самостоятельно**

---

#### Preconditions (Hard)
Вход **запрещён**, если:
- `market_regime != TREND`
- тренд не подтверждён (нет HH/HL или LL/LH)
- активен `ImpulseGuard` (хаотичный импульс)
- bid/ask spread > `max_spread_pct`
- ликвидность ниже `min_depth`
- активен `LatencyGuard`
- активен SAFE или PANIC режим

---

#### Detection Logic (Trend & Pullback)

Тренд считается валидным, если:
- сформирована устойчивая структура:
  - **LONG:** higher high + higher low
  - **SHORT:** lower low + lower high
- направление подтверждено объёмом
- отсутствуют признаки распределения

Pullback считается валидным, если:
- откат происходит **без импульса против тренда**
- глубина отката ограничена (`pullback_depth_pct`)
- цена удерживается выше/ниже ключевого уровня тренда

Фиксируются параметры:
- `trend_direction`
- `trend_strength_score`
- `pullback_depth_pct`
- `pullback_duration_sec`

---

#### Entry Logic (Continuation)

Вход **только после завершения отката**:
- цена перестала углублять pullback
- появляется возобновление движения по тренду
- подтверждение микро-импульсом в сторону тренда

**Entry:**
- **type:** `LIMIT` (по умолчанию)
- **direction:** по направлению тренда
- **entry_price:**
  - в зоне окончания pullback
  - не на самом экстремуме

---

#### Exit Logic

**Take Profit**
- основной: `trailing stop` по структуре тренда
- допускается partial TP на extension

**Stop Loss**
- обязательный `hard SL`
- за экстремумом pullback

**Time Stop**
- если возобновление тренда не произошло в течение `time_stop_sec` → `EXIT`

**Emergency Exit**
- слом структуры тренда
- резкий импульс против позиции
- срабатывание `ImpulseGuard`

---

#### State Machine

**States:**
- `IDLE`
- `SCANNING`
- `TREND_CONFIRMED`
- `PULLBACK_DETECTED`
- `WAIT_RESUME`
- `ENTERING`
- `ACTIVE`
- `EXITING`
- `COOLDOWN`
- `CLOSED`
- `ERROR_HALT`

**Invariants:**
- вход запрещён до `WAIT_RESUME`
- не более **1 активной позиции**
- входы **только по направлению тренда**
- усреднение запрещено

---

#### Risk & Limits
- `max_position_pct_of_equity`: **MEDIUM**
- `max_trades_per_trend`: ограничено
- усреднение **запрещено**
- `cooldown_after_trade_sec`: обязателен

---

#### Execution Rules
- entry: `LIMIT` preferred
- допускается `MARKET` **только** для emergency exit
- retries: ограничены
- partial fill:
  - остаток отменяется
  - исполненная часть управляется стандартно
- `SlippageGuard` обязателен

---

#### Execution Failure Matrix
- **Reject** → retry → `COOLDOWN`
- **Partial fill** → cancel remainder → manage position
- **Timeout** → cancel → `COOLDOWN`
- **Trend structure broken** → immediate `EXIT`
- **Data staleness** → cancel all → `ERROR_HALT`

---

#### Observability

**Events**
- `trend_confirmed`
- `pullback_detected`
- `resume_signal_detected`
- `entry_submitted`
- `entry_filled`
- `trailing_stop_updated`
- `trend_exit`
- `stop_loss_hit`
- `state_transition`

**Metrics**
- `trend_entries`
- `winrate`
- `avg_trend_duration`
- `avg_pullback_depth`
- `trailing_stop_efficiency`
- `trend_pnl`

---

#### SIM / REAL Split

**REAL**
- полная логика детекта тренда, pullback и исполнения
- корректная работа при `SIM = OFF`

**SIM (optional)**
- анализ качества трендов
- подбор параметров `pullback_depth_pct` и `time_stop_sec`

---

#### Status
**Draft → Candidate**

====================================================================================================

## Appendix: MoonBot Reference Mapping (Non-Normative)

Это приложение предназначено только для исторической и концептуальной справки.
Приведенные ниже термины MoonBot послужили основой для обозначения внутренних показателей,
но не определяют поведение стратегии, параметры или логику выполнения.

- MoonBot TimeInterval → tz_time_interval_sec
- MoonBot TradesDensity → tz_trades_density_pct
- MoonBot TradesDensityPrev → tz_trades_density_prev_pct
- MoonBot TradesCountMin → tz_trades_count_min_per_bin
- MoonBot PriceIntervals → tz_price_intervals
- MoonBot PriceIntervalShift → tz_price_interval_shift
- MoonBot PriceSpread → tz_price_spread_min_pct
- MoonBot IntervalsForBuySpread → tz_intervals_for_zone_calc
- MoonBot BuyPriceInSpread → tz_entry_level_pct
- MoonBot SellPriceInSpread → tz_exit_level_pct
- MoonBot BuyOrderReduce → entry_microvolume_reduce_ms
- MoonBot MinReducedSize → entry_min_notional
- MoonBot SpreadRepeatIfProfit → repeat_if_profit_pct

Non-normative. Informational only.

==================================================STRATEGY_STATUS==================================================

### Strategy Lifecycle Status

- **Active**
  - Strategy #1 — Rocket + 2 Anchors

- **Candidate**
  - Strategy #2 — Impulse Catcher
  - Strategy #6 — Spread Scalper

- **Draft**
  - Strategy #3 — Range Reversion
  - Strategy #4 — Trend Rider
  - Strategy #5 — Momentum Breakout
  - Strategy #7 — Liquidity Sweep Fade
  - Strategy #8 — Failed Breakout Reversion
  - Strategy #9 — Session Open Range Play
  - Strategy #10 — Trend Pullback Continuation

**Rule:**  
Draft-стратегии не допускаются в REAL без смены статуса.
