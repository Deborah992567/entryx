# EntryX Testing Strategy

Every phase ships tests before it is considered complete. Financial calculations get
deterministic tests with fixed inputs and expected outputs.

## Layers

### Unit (fast, isolated)
- `backend/tests/unit/` — security (Argon2 verify, JWT round-trip, token expiry/revocation),
  config parsing, indicator math (SMA/EMA/RSI/MACD vs hand-computed vectors), risk math
  (position size, RR, exposure, margin), market-structure detectors (BOS/CHoCH/FVG on
  synthetic price series), broker simulation fills, AI provider registry/health mapping.

### Integration (real components, no network)
- `backend/tests/integration/` — repository CRUD against SQLite, workspace layout persistence,
  order lifecycle through paper broker + trading service, WebSocket hub subscribe/broadcast.

### API (FastAPI TestClient)
- `backend/tests/api/` — auth (register/login/refresh/logout, rate limit, invalid tokens),
  workspace CRUD, health/status, error envelope consistency. Every endpoint has happy-path
  + negative tests.

### WebSocket
- `backend/tests/ws/` — connect with/without token, subscribe/unsubscribe, event fan-out,
  channel authorization boundaries (user A cannot see user B's positions).

### Security
- `backend/tests/security/` — password hashing, token tampering, secret redaction in audit
  logs, no credential leakage in API responses, brute-force rate limiting.

### Frontend (Flutter/Dart)
- `frontend/test/**` — `flutter test` + `mocktail`: auth flow, workspace dock
  (resize/collapse/rearrange pure logic), connection-status store, market tick updates,
  REST/WS client parsing against fixtures.

### Deterministic financial tests
Every numeric function that affects money must have fixed-input tests:
- position size from risk %, SL distance, balance;
- floating P&L for buy/sell at known prices;
- swap/commission application;
- backtester fill logic incl. spread/slippage and SL/TP ordering within a bar;
- margin & margin-level math;
- metrics (win rate, profit factor, max drawdown, Sharpe, expectancy) on a known trade list.

## Test tooling

| Area | Tool |
|---|---|
| Backend | pytest, pytest-asyncio, httpx/TestClient, pytest-cov, ruff |
| Frontend | flutter test, mocktail |
| CI | GitHub Actions (install deps, run backend + frontend suites, upload coverage) |

## Conventions

- Tests live next to code by mirroring `app/` layout under `backend/tests/`.
- Fixtures: `conftest.py` provides `db_session` (SQLite in-memory), `client` (TestClient),
  `user_factory`, `account_factory`, `symbol_factory`.
- Randomized data generators (seeded) for backtest/indicator tests.
- Coverage floor: Phase 1 ≥ 80% on core (security, auth, db); raised per phase.
- Slow/nightly suites (long backtests, full optimizer sweeps) tagged `slow`.

## CI

`.github/workflows/ci.yml`: on push/PR — backend: lint (ruff) + pytest; frontend: `flutter analyze` + `flutter test`.
