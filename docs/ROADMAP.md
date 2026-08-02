# EntryX Technical Roadmap

Build order follows the development phases in the project brief. Each phase ends with a
working, tested, committed state. Nothing moves forward while a core subsystem is broken.

Legend: `[x]` done · `[~]` in progress · `[ ]` planned

## PHASE 1 — Foundation

- [~] Project architecture & contracts (`docs/`)
- [x] Repo + GitHub CI scaffolding
- [ ] Backend core: config, logging, security (JWT/Argon2), exceptions
- [ ] Database: SQLAlchemy models + Alembic migrations (MariaDB; SQLite dev fallback)
- [ ] Auth API: register / login / refresh / me / logout (+ rate limiting, audit log)
- [ ] Workspace layout persistence API (`chart_layouts`)
- [ ] Health + status API; WebSocket hub skeleton with JWT auth
- [ ] Desktop shell: Flutter app, TopBar, workspace dock system
  (resize/collapse/rearrange/persist), connection status
- [ ] Placeholder panels: MarketWatch, Chart, AI Copilot, Trading Terminal
- [ ] Auth UI: login / register screen, token refresh, secure storage

## PHASE 2 — Market data + Paper broker + Real-time

- [ ] `MarketDataProvider` interface + simulated deterministic provider
- [ ] `BrokerAdapter` interface + `PaperBroker` (virtual accounts, deposits, fills)
- [ ] Market Watch panel: symbols, bid/ask/spread/change/volume, search/favorites/categories
- [ ] WebSockets: tick/candle broadcasting to panels; account/P&L events
- [ ] Order/position REST + WS lifecycle on the paper broker

## PHASE 3 — Chart engine + indicators + drawings

- [ ] Canvas chart engine: candlesticks, volume, timeframes (M1…MN1), zoom/pan/crosshair
- [ ] Price scale, time scale, auto-scroll, multiple charts, split views, synced charts
- [ ] Indicator engine (common interface): SMA, EMA, WMA, VWAP, RSI, MACD, Stochastic,
  ATR, ADX, CCI, ROC, Momentum, Bollinger, Ichimoku, PSAR, OBV, volume
- [ ] Drawing tools: trendline, h/v lines, ray, channel, rectangle, ellipse, arrow, text,
  Fibonacci retrace/extension/fan, pitchfork, S/R — movable/editable/persistent
- [ ] Chart templates, themes, layout persistence integration

## PHASE 4 — Trading engine + risk

- [ ] Order types: market, limit/stop variants incl. stop-limit; SL/TP, magic, comment, expiry
- [ ] Position management: open/close/partial close, modify SL/TP, trailing stop
- [ ] Account: balance, equity, margin, free margin, margin level, floating/realized P&L,
  commission, swap, exposure
- [ ] Risk engine (UI-independent): position sizing, risk %, RR, exposure, margin, limits
- [ ] Trading Terminal tabs: Positions, Orders, History, Account, Journal, Alerts, Experts, Logs

## PHASE 5 — Strategy + Backtesting + Optimization

- [ ] Strategy framework: `initialize/on_tick/on_candle/on_signal/on_order/on_position/shutdown`
- [ ] Backtester: candle/tick replay, commission/spread/slippage/swap/leverage, SL/TP/trailing
- [ ] Metrics: trades, win rate, PF, max DD, Sharpe, expectancy, equity curve
- [ ] Visual backtest results on chart; parameter optimization with overfit warnings

## PHASE 6 — Market structure + Smart Money Concepts

- [ ] Deterministic detectors: swing H/L, HH/HL/LH/LL, BOS, CHoCH, trend/range, breakout/retest
- [ ] FVG, order blocks, breaker blocks, liquidity pools, EQH/EQL, sweeps, displacement,
  premium/discount — each object has ts, timeframe, range, strength, status, invalidation
- [ ] Chart rendering of detected structures

## PHASE 7 — Local AI infrastructure

- [ ] `AIProvider` abstraction: `generate/stream/analyze/embed/health_check`
- [ ] `OllamaProvider`, model registry + selection (Llama/Qwen/Mistral families), health UI
- [ ] AI feature pipeline: market data → features → analysis → explanation
- [ ] AI Copilot panel (chat grounded in real EntryX data, never invented)

## PHASE 8 — AI applications

- [ ] Chart Explainer ("Explain This Chart") with structured output + honest uncertainty
- [ ] Market Scanner (multi-symbol/timeframe setups, filters)
- [ ] Strategy Builder (NL → rules → backtest; no auto-live deploy)
- [ ] Risk Copilot (pre-trade risk explanation)
- [ ] Trading Journal analysis (patterns, overtrading, time-of-day, strategy/symbol perf)

## PHASE 9 — Broker adapters + live safeguards

- [ ] Additional broker adapters behind `BrokerAdapter`
- [ ] Live-trading safeguards: opt-in, validation, risk limits, paper validation,
  LIVE confirmation, kill switch, full decision/execution logging

## PHASE 10 — Hardening

- [ ] Full unit/integration/API/WS/db/security test matrix
- [ ] Performance: chart rendering, backtest speed, WS fan-out
- [ ] Packaging (Tauri desktop bundle, installer), deployment docs

---

## Cross-cutting

- Observability: structured logging, health/status surfaces, metrics
- Security: Argon2, JWT, encrypted secrets, audit log, rate limiting, CSRF/validation
- Testing: deterministic financial-calc tests; every phase adds tests before moving on

## Status per phase

| Phase | Title | Status |
|---|---|---|
| 1 | Foundation | in progress |
| 2 | Market data + paper broker + real-time | planned |
| 3 | Chart engine + indicators + drawings | planned |
| 4 | Trading engine + risk | planned |
| 5 | Strategy + backtesting + optimization | planned |
| 6 | Market structure + SMC | planned |
| 7 | Local AI infrastructure | planned |
| 8 | AI applications | planned |
| 9 | Broker adapters + live safeguards | planned |
| 10 | Hardening + packaging | planned |
