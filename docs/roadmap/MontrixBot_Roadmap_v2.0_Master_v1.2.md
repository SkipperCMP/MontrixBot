
<a name="montrixbot-roadmap-v2-0-master-v1-1"></a>
# MontrixBot_Roadmap_v2.0_Master_v1.1

<a name="0-how-to-read-this-roadmap"></a>
## 0. How to Read This Roadmap
- Extended = long-term strategy.
- Roadmap A = architectural sequence.
- Roadmap B = execution status.
- Workflow: Extended → A → B.

<a name="0-3-step-lifecycle"></a>
## 0.3 Step Lifecycle
PLANNED → ACTIVE → DONE → ARCHIVED.

<a name="0-4-step-transition-rules"></a>
## 0.4 Step Transition Rules
Переход к следующему STEP допустим только если:
- предыдущий STEP = DONE,
- baseline создан,
- Roadmap B обновлён,
- MasterRules не требует исправлений.

<a name="0-5-cross-references"></a>
## 0.5 Cross-References
- Extended ↔ A ↔ B связаны логически и не конфликтуют.
- Assistant обязан следовать ссылкам между документами.

<a name="0-6-dependencies-table"></a>
## 0.6 Dependencies Table
- 1.3.3 зависит от 1.3.2
- 1.3.2 зависит от 1.3.1
- 2.0 зависит от завершения блока 1.x
- 3.x зависит от завершения 2.x

<a name="0-7-versioning-rules"></a>
## 0.7 Versioning Rules
- v2.0 = базовая структура
- v2.1+ = структурные изменения
- v3.0 = стратегические изменения

<a name="0-8-assistant-actions-global"></a>
## 0.8 Assistant Actions (Global)
Assistant MUST:
- проверять статус в B,
- соблюдать порядок шагов по A,
- производить патчи только в ACTIVE-шаге,
- обновлять Roadmap B после завершения,
- сверяться с Extended при стратегических изменениях.




<a name="montrixbot-roadmap-v2-0-master-v1-0"></a>
# MontrixBot_Roadmap_v2.0_Master_v1.0

<a name="0-roadmap-hierarchy-sync-rules"></a>
## 0. Roadmap Hierarchy & Sync Rules

- Extended defines long-term strategy.
- Roadmap A defines architectural sequence.
- Roadmap B defines current execution state.
- No file overrides another; they complement each other.
- Baseline naming always follows Roadmap A + Roadmap B status.

<a name="1-extended-strategic-roadmap"></a>
## 1. Extended Strategic Roadmap

MontrixBot Roadmap v2.0 Extended Edition + STATUS
1.x — Core Trading Engine (Фундамент)
Цель: полностью рабочий, стабильный торговый движок с UI, SIM, TPSL и риск-менеджментом.
1.1 — Основа ядра — ACTIVE / 90% DONE
✔ SIM/REAL Engine — ACTIVE → стабильный
✔ TPSL Loop v1 — ACTIVE / 80% готов
✔ State Engine + StateBinder — ACTIVE
✔ Executor (SIM/REAL) — ACTIVE
✔ Market Orders — DONE
✔ Basic Filters (EMA/Volume/News) — DONE
✔ UI: график, панель сделок, статус-бар — ACTIVE
✔ Сделочный журнал (core) — ACTIVE
1.2 — Надёжность и безопасность — ACTIVE / частично DONE
Автовосстановление состояния (SIM/REAL) — ACTIVE
Crash-proof engine — PLANNED
Watchdog deep-level — PLANNED
Failover REST/WebSocket — PLANNED
Throttling всех API — DONE
2FA защита — DONE
Авто-проверка minQty/minNotional — DONE
Panic-Kill — PLANNED
1.3 — Расширенный UI (Trading Desk v1) — ACTIVE
Панель активных сделок — ACTIVE
Статус-бар расширенный — ACTIVE
Deals Journal UI — ACTIVE
Ticker Panel — ACTIVE
Controls Bar — DONE
Mini-equity bar — ACTIVE
Local notifications — PLANNED
Chart overlays — ACTIVE
1.4 — Риск-менеджмент базового уровня — ACTIVE
Балансовые лимиты — DONE
Max active positions — PLANNED
Auto-risk throttling — PLANNED
Basic stop-protection — DONE
Session P/L, daily P/L — PLANNED
SL-трейлинг умный — ACTIVE
1.5 — Сделочный журнал / Аналитика (v1) — ACTIVE
Equity chart — ACTIVE
Win-rate, pnl, длительность — ACTIVE
Разрез по монетам — PLANNED
Экспорт истории — PLANNED
2.x — Advanced Trading Suite (профессиональная платформа)
2.1 — Risk Engine PRO — PLANNED
VaR / CVaR — PLANNED
Volatility sizing — PLANNED
Expected drawdown — PLANNED
Max exposure — PLANNED
SL-grids — PLANNED
Heatmap риска — PLANNED
Auto-risk reduction — PLANNED
2.2 — Advanced Filters Pack — PLANNED
Orderflow filter — PLANNED
Liquidity filter — PLANNED
Spread/slippage detector — PLANNED
Market regime detector — PLANNED
Momentum filter — PLANNED
Correlation filter — PLANNED
RSI/MACD/BB/ATR modules — PLANNED
Filter chains v2 — PLANNED
2.3 — Trading Desk UI v2 — PLANNED
Watchlist — PLANNED
Heatmap монет — PLANNED
Multi-chart — PLANNED
Drag & drop layout — LATER
Layout Profiles — LATER
Alerts Panel — PLANNED
Real-time event log — PLANNED
L2/Orderbook mini-panel — PLANNED
2.4 — Trade Analytics v2 — PLANNED
Profit factor / SQN — PLANNED
Weekly/monthly analytics — PLANNED
Exposure chart — PLANNED
Strategy comparison — LATER
PDF/Excel reports — PLANNED
3.x — AI, Multi-Exchange, Automation Platform
3.1 — Multi-Exchange Engine — PLANNED
Kraken — PLANNED
Bybit — PLANNED
KuCoin — PLANNED
Unified Exchange Layer — PLANNED
Exchange switcher in UI — PLANNED
Cross-exchange sync — LATER
Exchange health checker — PLANNED
3.2 — AI Trading Engine — PLANNED
AI Scoring монет — PLANNED
AI Trend classifier — PLANNED
ML TP/SL optimizer — LATER
Volatility predictor — LATER
AI Risk Advisor — LATER
AI Portfolio Rotation — LATER
AutoML tuning — LATER
Breakout detector ML — LATER
3.3 — Strategy Automation Layer — PLANNED
Wizard-конструктор стратегий — PLANNED
Strategy-as-Code — LATER
Plugin AI modules — PLANNED
Backtest Engine v2 — LATER
Forward-test engine — LATER
Optimizer Grid / Bayesian — LATER
3.4 — Pro Operations — PLANNED
Sessions — PLANNED
Portfolio profiles — PLANNED
Multi-account trade router — LATER
Alerts→Actions automations — PLANNED
4.x — Экосистема (Cloud, Mobile, Marketplace)
4.1 — Mobile App (iOS/Android) — LATER
Monitoring — LATER
Quick actions — LATER
Push — LATER
Mobile dashboards — LATER
4.2 — Cloud Platform — LATER
Cloud sync — LATER
Remote control — LATER
Cloud logs — LATER
Backup states — LATER
API integration — LATER
4.3 — Marketplace — LATER
Strategies marketplace — LATER
Indicators — LATER
Filters — LATER
AI models — LATER
Licensing system — PLANNED (базовая)
Ratings — LATER
4.4 — Community Layer — LATER
Profiles — LATER
Leaderboards — LATER
Shareable backtests — LATER
Public portfolios — LATER
Авторские стратегии — LATER
Built-in chat — LATER

<a name="2-roadmap-a-architectural-structure"></a>
## 2. Roadmap A — Architectural Structure

<a name="montrixbot-roadmap-v2-0-full-a-md"></a>
# MontrixBot_Roadmap_v2.0_full_A.md
<a name="a-reformatted-original-roadmap-linear-must-should"></a>
## Раздел A — Reformatted Original Roadmap (Linear + MUST/SHOULD)

<a name="1-0-must-ui-foundation-engine-bootstrap"></a>
# Этап 1.0 — MUST — UI Foundation & Engine Bootstrap
<a name="1-0-1-ui-must"></a>
## 1.0.1 — Базовые элементы UI — MUST
- структура окна, кнопки, меню
<a name="1-0-2-must"></a>
## 1.0.2 — Панель режимов — MUST
- переключение SIM/REAL
<a name="1-0-3-notebook-must"></a>
## 1.0.3 — Вкладки Notebook — MUST
- чарт, сигналы, сделки
<a name="1-0-4-uiapi-must"></a>
## 1.0.4 — Структура UIAPI — MUST
- связь UI ↔ Engine
<a name="1-0-5-snapshot-must"></a>
## 1.0.5 — Snapshot-модели — MUST
- формат снапшотов
<a name="1-0-6-stateengine-init-must"></a>
## 1.0.6 — StateEngine init — MUST
- инициализация ядра

<a name="1-1-must-binder-loops"></a>
# Этап 1.1 — MUST — Binder & Loops
<a name="1-1-1-bindings-ui-engine-must"></a>
## 1.1.1 — Bindings UI → Engine — MUST
- маршрутизация взаимодействия
<a name="1-1-2-must"></a>
## 1.1.2 — Фиксация ошибок — MUST
- fail-fast, recovery
<a name="1-1-3-runtime-sync-must"></a>
## 1.1.3 — Runtime Sync — MUST
- синхронизация потоков

<a name="1-2-must-tpsl-loop-integration"></a>
# Этап 1.2 — MUST — TPSL Loop & Integration
<a name="1-2-1-sim-must"></a>
## 1.2.1 — Трейлинг в SIM — MUST
<a name="1-2-2-hook-executor-must"></a>
## 1.2.2 — Hook Executor — MUST
<a name="1-2-3-tpsl-stability-must"></a>
## 1.2.3 — TPSL Stability — MUST
<a name="1-2-4-must"></a>
## 1.2.4 — Панель активных сделок — MUST
<a name="1-2-5-must"></a>
## 1.2.5 — Сделочный журнал — MUST
<a name="1-2-6-must"></a>
## 1.2.6 — Статус-бар — MUST
<a name="1-2-7-baseline-clean-must"></a>
## 1.2.7 — Baseline-Clean — MUST

<a name="1-3-must-runtime-hooks"></a>
# Этап 1.3 — MUST — Runtime Hooks
<a name="1-3-1-runtime-load-must"></a>
## 1.3.1 — Runtime-Load — MUST
<a name="1-3-2-runtime-save-must"></a>
## 1.3.2 — Runtime-Save — MUST
<a name="1-3-3-must"></a>
## 1.3.3 — Резервы — MUST

<a name="1-4-must-safety-systems"></a>
# Этап 1.4 — MUST — Safety Systems
<a name="1-4-1-heartbeat-must"></a>
## 1.4.1 — Heartbeat — MUST
<a name="1-4-2-delay-detector-must"></a>
## 1.4.2 — Delay Detector — MUST
<a name="1-4-3-time-integrity-must"></a>
## 1.4.3 — Time Integrity — MUST
<a name="1-4-4-log-history-retention-must"></a>
## 1.4.4 — Log & History Retention — MUST

<a name="1-5-must-ui-polish"></a>
# Этап 1.5 — MUST — UI Polish
<a name="1-5-1-mini-equity-bar-must"></a>
## 1.5.1 — Mini Equity Bar — MUST
<a name="1-5-2-status-indicators-must"></a>
## 1.5.2 — Status Indicators — MUST
<a name="1-5-3-must"></a>
## 1.5.3 — График обновлений — MUST

<a name="1-6-must-active-positions-panel-2-0"></a>
# Этап 1.6 — MUST — Active Positions Panel 2.0
<a name="1-6-1-must"></a>
## 1.6.1 — Улучшенный интерфейс — MUST
<a name="1-6-2-pnl-must"></a>
## 1.6.2 — PnL-карточки — MUST
<a name="1-6-3-must"></a>
## 1.6.3 — Сигналы — MUST

<a name="1-7-must-deals-journal-2-0"></a>
# Этап 1.7 — MUST — Deals Journal 2.0
<a name="1-7-1-must"></a>
## 1.7.1 — Фильтры — MUST
<a name="1-7-2-must"></a>
## 1.7.2 — Поиск — MUST
<a name="1-7-3-must"></a>
## 1.7.3 — Детализация — MUST

<a name="1-8-must-modular-ui-architecture"></a>
# Этап 1.8 — MUST — Modular UI Architecture
<a name="1-8-1-must"></a>
## 1.8.1 — Вынести виджеты — MUST
<a name="1-8-2-uiapi-must"></a>
## 1.8.2 — Унификация UIAPI — MUST
<a name="1-8-3-snapshot-must"></a>
## 1.8.3 — Snapshot-пайплайн — MUST
<a name="1-8-4-ui-must"></a>
## 1.8.4 — Рефакторинг UI — MUST
<a name="1-8-5-must"></a>
## 1.8.5 — Потоки обновления — MUST

<a name="1-9-must-multi-strategy-portfolio"></a>
# Этап 1.9 — MUST — Multi-Strategy Portfolio
<a name="1-9-1-trio-mode-must"></a>
## 1.9.1 — Trio Mode — MUST
<a name="1-9-2-top-k-must"></a>
## 1.9.2 — Top-K — MUST
<a name="1-9-3-must"></a>
## 1.9.3 — Ограничения долей — MUST
<a name="1-9-4-must"></a>
## 1.9.4 — Анти-корреляция — MUST
<a name="1-9-5-scoring-must"></a>
## 1.9.5 — Scoring-модель — MUST
<a name="1-9-6-auto-manual-switch-must"></a>
## 1.9.6 — Auto/Manual Switch — MUST

<a name="1-10-must-tradingview-ai"></a>
# Этап 1.10 — MUST — TradingView & AI
<a name="1-10-1-tv-alerts-must"></a>
## 1.10.1 — TV Alerts — MUST
<a name="1-10-2-ai-signals-must"></a>
## 1.10.2 — AI Signals — MUST
<a name="1-10-3-trend-visualization-must"></a>
## 1.10.3 — Trend Visualization — MUST

<a name="1-11-must-auto-balancing"></a>
# Этап 1.11 — MUST — Auto-Balancing
<a name="1-11-1-online-must"></a>
## 1.11.1 — Online Оценка — MUST
<a name="1-11-2-auto-rebalance-must"></a>
## 1.11.2 — Auto Rebalance — MUST
<a name="1-11-3-cooldown-must"></a>
## 1.11.3 — Cooldown — MUST
<a name="1-11-4-copy-trading-sim-must"></a>
## 1.11.4 — Copy-Trading SIM — MUST

<a name="1-12-must-license-manager-v1"></a>
# Этап 1.12 — MUST — License Manager v1
<a name="1-12-1-license-system-must"></a>
## 1.12.1 — License System — MUST
<a name="1-12-2-security-must"></a>
## 1.12.2 — Security — MUST
<a name="1-12-3-feature-limits-must"></a>
## 1.12.3 — Feature Limits — MUST

<a name="2-0-must-real-copy-trading"></a>
# Этап 2.0 — MUST — REAL Copy-Trading
<a name="2-0-1-real-copy-trading-must"></a>
## 2.0.1 — REAL Copy-Trading — MUST
<a name="2-0-2-ai-model-v2-must"></a>
## 2.0.2 — AI Model v2 — MUST

<a name="3-0-should-ecosystem"></a>
# Этап 3.0 — SHOULD — Ecosystem
<a name="3-0-1-cloud-backup-should"></a>
## 3.0.1 — Cloud Backup — SHOULD
<a name="3-0-2-marketplace-should"></a>
## 3.0.2 — Marketplace — SHOULD
<a name="3-0-3-web-dashboard-should"></a>
## 3.0.3 — Web Dashboard — SHOULD
<a name="3-0-4-api-plugins-should"></a>
## 3.0.4 — API Plugins — SHOULD

<a name="3-1-should-ideal-roadmap"></a>
# Этап 3.1 — SHOULD — IDEAL ROADMAP
<a name="3-1-1-orderflow-meter-should"></a>
## 3.1.1 — Orderflow Meter — SHOULD
<a name="3-1-2-delta-pressure-should"></a>
## 3.1.2 — Delta-pressure — SHOULD
<a name="3-1-3-microstructure-scanner-should"></a>
## 3.1.3 — Microstructure Scanner — SHOULD
<a name="3-1-4-latency-map-should"></a>
## 3.1.4 — Latency Map — SHOULD
<a name="3-1-5-lstm-transformer-should"></a>
## 3.1.5 — LSTM/Transformer — SHOULD
<a name="3-1-6-bandit-switch-should"></a>
## 3.1.6 — Bandit Switch — SHOULD
<a name="3-1-7-pre-pump-detection-should"></a>
## 3.1.7 — Pre-pump Detection — SHOULD
<a name="3-1-8-spread-anomaly-should"></a>
## 3.1.8 — Spread Anomaly — SHOULD
<a name="3-1-9-zero-lag-ui-should"></a>
## 3.1.9 — Zero-lag UI — SHOULD
<a name="3-1-10-heatmaps-should"></a>
## 3.1.10 — Heatmaps — SHOULD
<a name="3-1-11-multi-chart-workspace-should"></a>
## 3.1.11 — Multi-chart Workspace — SHOULD
<a name="3-1-12-trader-profile-should"></a>
## 3.1.12 — Trader Profile — SHOULD
<a name="3-1-13-strategy-marketplace-should"></a>
## 3.1.13 — Strategy Marketplace — SHOULD
<a name="3-1-14-mobile-app-should"></a>
## 3.1.14 — Mobile App — SHOULD
<a name="3-1-15-community-hub-should"></a>
## 3.1.15 — Community Hub — SHOULD


<a name="3-roadmap-b-execution-status"></a>
## 3. Roadmap B — Execution Status

<a name="montrixbot-roadmap-v2-0-full-b-md"></a>
# MontrixBot_Roadmap_v2.0_full_B.md
<a name="b-roadmap-v2-0-statuses-must-should"></a>
## Раздел B — Roadmap v2.0 (Statuses + MUST/SHOULD)

<a name="1-0-must-core-foundations"></a>
# Этап 1.0 — MUST — Core Foundations
<a name="1-0-1-ui-foundation-done-must"></a>
## 1.0.1 — UI Foundation — DONE — MUST
- базовые элементы UI
<a name="1-0-2-stateengine-core-done-must"></a>
## 1.0.2 — StateEngine Core — DONE — MUST
- тик-движок
<a name="1-0-3-uiapi-base-done-must"></a>
## 1.0.3 — UIAPI Base — DONE — MUST
- контракт UI ↔ Engine

<a name="1-1-must-binder-runtime"></a>
# Этап 1.1 — MUST — Binder & Runtime
<a name="1-1-1-statebinder-done-must"></a>
## 1.1.1 — StateBinder — DONE — MUST
<a name="1-1-2-runtime-sync-done-must"></a>
## 1.1.2 — Runtime Sync — DONE — MUST
<a name="1-1-3-error-fixation-done-must"></a>
## 1.1.3 — Error Fixation — DONE — MUST

<a name="1-2-must-tpsl-ui-integration"></a>
# Этап 1.2 — MUST — TPSL + UI Integration
<a name="1-2-1-tpsl-stabilization-done-must"></a>
## 1.2.1 — TPSL Stabilization — DONE — MUST
<a name="1-2-2-runtime-tpsl-loop-done-must"></a>
## 1.2.2 — Runtime TPSL Loop — DONE — MUST
<a name="1-2-3-full-ui-integration-done-must"></a>
## 1.2.3 — Full UI Integration — DONE — MUST
<a name="1-2-4-replacelogic-core-done-must"></a>
## 1.2.4 — ReplaceLogic Core — DONE — MUST
<a name="1-2-5-ui-polish-done-must"></a>
## 1.2.5 — UI Polish — DONE — MUST
<a name="1-2-6-status-bar-done-must"></a>
## 1.2.6 — Status Bar — DONE — MUST
<a name="1-2-7-baseline-clean-done-must"></a>
## 1.2.7 — Baseline-Clean — DONE — MUST


<a name="1-3-must-modular-ui-architecture"></a>
# Этап 1.3 — MUST — Modular UI Architecture
<a name="1-3-1-widget-separation-done-must"></a>
## 1.3.1 — Widget Separation — DONE — MUST
<a name="1-3-2-update-router-planned-must"></a>
## 1.3.2 — Update Router — PLANNED — MUST
<a name="1-3-3-equity-chart-planned-must"></a>
## 1.3.3 — Equity Chart — PLANNED — MUST

<a name="1-4-must-multi-strategy-portfolio"></a>
# Этап 1.4 — MUST — Multi-Strategy Portfolio
<a name="1-4-1-trio-mode-not-started-must"></a>
## 1.4.1 — Trio Mode — NOT STARTED — MUST
<a name="1-4-2-top-k-not-started-must"></a>
## 1.4.2 — Top-K — NOT STARTED — MUST
<a name="1-4-3-constraints-not-started-must"></a>
## 1.4.3 — Constraints — NOT STARTED — MUST
<a name="1-4-4-log-history-retention-not-started-must"></a>
## 1.4.4 — Log & History Retention — NOT STARTED — MUST

<a name="1-5-must-tradingview-ai"></a>
# Этап 1.5 — MUST — TradingView & AI
<a name="1-5-1-tradingview-alerts-not-started-must"></a>
## 1.5.1 — TradingView Alerts — NOT STARTED — MUST
<a name="1-5-2-ai-signals-v1-not-started-must"></a>
## 1.5.2 — AI Signals v1 — NOT STARTED — MUST
<a name="1-5-3-ai-ui-not-started-must"></a>
## 1.5.3 — AI UI — NOT STARTED — MUST

<a name="1-6-must-auto-balancing"></a>
# Этап 1.6 — MUST — Auto-Balancing
<a name="1-6-1-score-engine-not-started-must"></a>
## 1.6.1 — Score Engine — NOT STARTED — MUST
<a name="1-6-2-rebalance-not-started-must"></a>
## 1.6.2 — Rebalance — NOT STARTED — MUST
<a name="1-6-3-cooldown-not-started-must"></a>
## 1.6.3 — Cooldown — NOT STARTED — MUST
<a name="1-6-4-copy-trading-sim-not-started-must"></a>
## 1.6.4 — Copy-Trading SIM — NOT STARTED — MUST

<a name="1-7-must-license-manager"></a>
# Этап 1.7 — MUST — License Manager
<a name="1-7-1-key-manager-not-started-must"></a>
## 1.7.1 — Key Manager — NOT STARTED — MUST
<a name="1-7-2-feature-limiter-not-started-must"></a>
## 1.7.2 — Feature Limiter — NOT STARTED — MUST

<a name="2-0-must-real-copy-trading"></a>
# Этап 2.0 — MUST — REAL Copy-Trading
<a name="2-0-1-real-copy-trading-not-started-must"></a>
## 2.0.1 — REAL Copy-Trading — NOT STARTED — MUST
<a name="2-0-2-ai-v2-not-started-must"></a>
## 2.0.2 — AI v2 — NOT STARTED — MUST

<a name="2-1-must-bandits"></a>
# Этап 2.1 — MUST — Bandits
<a name="2-1-1-bandit-model-not-started-must"></a>
## 2.1.1 — Bandit Model — NOT STARTED — MUST
<a name="2-1-2-online-learning-not-started-must"></a>
## 2.1.2 — Online Learning — NOT STARTED — MUST

<a name="2-2-must-auto-tuning"></a>
# Этап 2.2 — MUST — Auto-Tuning
<a name="2-2-1-period-tuning-not-started-must"></a>
## 2.2.1 — Period Tuning — NOT STARTED — MUST
<a name="2-2-2-weight-tuning-not-started-must"></a>
## 2.2.2 — Weight Tuning — NOT STARTED — MUST

<a name="3-0-should-ecosystem"></a>
# Этап 3.0 — SHOULD — Ecosystem
<a name="3-0-1-cloud-backup-not-started-should"></a>
## 3.0.1 — Cloud Backup — NOT STARTED — SHOULD
<a name="3-0-2-marketplace-not-started-should"></a>
## 3.0.2 — Marketplace — NOT STARTED — SHOULD
<a name="3-0-3-web-dashboard-not-started-should"></a>
## 3.0.3 — Web Dashboard — NOT STARTED — SHOULD
<a name="3-0-4-api-plugins-not-started-should"></a>
## 3.0.4 — API Plugins — NOT STARTED — SHOULD

<a name="3-1-should-ideal-roadmap"></a>
# Этап 3.1 — SHOULD — IDEAL ROADMAP
<a name="3-1-1-orderflow-imbalance-meter-should"></a>
## 3.1.1 — Orderflow Imbalance Meter — SHOULD
<a name="3-1-2-delta-pressure-analysis-should"></a>
## 3.1.2 — Delta-pressure Analysis — SHOULD
<a name="3-1-3-microstructure-scanner-should"></a>
## 3.1.3 — Microstructure Scanner — SHOULD
<a name="3-1-4-latency-map-should"></a>
## 3.1.4 — Latency Map — SHOULD
<a name="3-1-5-lstm-transformer-should"></a>
## 3.1.5 — LSTM/Transformer — SHOULD
<a name="3-1-6-bandit-switch-should"></a>
## 3.1.6 — Bandit Switch — SHOULD
<a name="3-1-7-pre-pump-detection-should"></a>
## 3.1.7 — Pre-pump Detection — SHOULD
<a name="3-1-8-spread-anomaly-should"></a>
## 3.1.8 — Spread Anomaly — SHOULD
<a name="3-1-9-zero-lag-ui-should"></a>
## 3.1.9 — Zero-lag UI — SHOULD
<a name="3-1-10-advanced-heatmaps-should"></a>
## 3.1.10 — Advanced Heatmaps — SHOULD
<a name="3-1-11-multi-chart-workspace-should"></a>
## 3.1.11 — Multi-chart Workspace — SHOULD
<a name="3-1-12-trader-profile-should"></a>
## 3.1.12 — Trader Profile — SHOULD
<a name="3-1-13-strategy-marketplace-should"></a>
## 3.1.13 — Strategy Marketplace — SHOULD
<a name="3-1-14-mobile-app-should"></a>
## 3.1.14 — Mobile App — SHOULD
<a name="3-1-15-community-hub-should"></a>
## 3.1.15 — Community Hub — SHOULD
