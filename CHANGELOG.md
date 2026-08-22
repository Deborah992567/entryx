# Changelog

## v0.9.0 (2026-08-22) — Session Progress

### Bug Fixes
- Auto-create SQLite tables on startup (`Base.metadata.create_all`) to fix empty DB on first run
- Catch-all exception handler returning consistent JSON error envelope
- Frontend error display shows message text instead of full exception toString
- Rate limit response uses consistent JSON error envelope format
- Fixed AI provider status message stale "Phase 7" reference

### Frontend
- Auth screen: `TextField` → `TextFormField` with email regex, password strength, and name validators
- Proper `TextInputAction` chaining for improved UX flow

### Test Suites Added
- Full auth flow integration test (register/login/me/refresh/logout)
- Risk engine edge case tests (stop distance, risk amount, RR ratios, custom limits)
- Market data API tests (symbols, candles, quote endpoints)
- Trading API tests (account, orders, positions, history, risk assessment)
- Technical indicator unit tests (SMA, EMA, RSI, ATR)
- Workspace layout CRUD API tests (list, create, update, delete)
- Strategy catalog and backtest API tests (catalog, instances, backtest run, 404 handling)
- JWT expiration and future token rejection tests
- Performance benchmarks (metrics, risk engine, indicators, WS fan-out, serialization)
- Security utils tests, logging filter tests, rate limiter tests, config tests

### Infrastructure
- `.dockerignore` file for smaller Docker builds
- `Makefile` with dev, test, lint, format, docker commands
- Docker deployment section and production checklist in DEPLOYMENT.md
- `X-API-Version` and `X-Powered-By` response headers
- Models package `__init__.py` with all exports for convenient imports
- Updated ROADMAP through Phase 10

### Code Quality
- Ruff formatting applied across all source files
- Field descriptions added for all schema models (Symbol, Order, Position, Account, Trade, Candle, Quote, Strategy, Backtest, Optimization, Auth, Workspace schemas)
- WS integration tests updated for welcome event consumption
