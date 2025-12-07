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