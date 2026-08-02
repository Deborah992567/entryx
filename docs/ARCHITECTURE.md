# EntryX Architecture

EntryX is a modular, provider-agnostic trading terminal. The architecture separates every
major subsystem behind explicit interfaces so that no subsystem is coupled to a specific
data provider, broker, database, or AI model.

## 1. System diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│  FRONTEND (Flutter desktop app — macOS/Windows/Linux)               │
│  TopBar · Workspace/dock system · MarketWatch · Chart · AI Copilot  │
│  Trading Terminal · Command palette · Theme · WS client · REST API  │
└───────────────┬───────────────────────────┬─────────────────────────┘
                │ REST (JSON)               │ WebSocket (events)
                ▼                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  BACKEND (FastAPI)                                                  │
│  ┌───────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────────────┐  │
│  │ Auth/RBAC │ │ REST API │ │ WS Hub    │ │ Services layer       │  │
│  │ JWT       │ │ v1       │ │ (events)  │ │ market/trading/risk │  │
│  └───────────┘ └──────────┘ └───────────┘ │ strategy/backtest/ai│  │
│                                           └──────────┬───────────┘  │
│  ┌──────────────────────────────────────────────────┐│              │
│  │ Provider adapters (interfaces)                  ││              │
│  │  MarketDataProvider  BrokerAdapter  AIProvider  ││              │
│  └──────────────────────────────────────────────────┘│              │
└──────────────┬───────────────┬───────────────┬───────┼──────────────┘
               ▼               ▼               ▼       ▼
          MariaDB        Redis (planned)   Ollama/local     Simulated
          (SQLite dev)                     models via        market data
                                            llama.cpp/HF      generator
```

Data flows one way for execution (AI → Strategy → Risk → Execution → Broker) and is
event-driven for everything real-time (prices, candles, orders, positions, P&L, alerts).

## 2. Module map

| Module | Location | Responsibility | Interface |
|---|---|---|---|
| Core | `backend/app/core` | config, security (JWT/passwords), structured logging, exceptions | — |
| DB | `backend/app/db` | SQLAlchemy 2 models, session, migrations (Alembic) | — |
| API | `backend/app/api/v1` | REST routers, validation, auth deps | OpenAPI |
| Schemas | `backend/app/schemas` | Pydantic request/response contracts | — |
| Services | `backend/app/services` | orchestration of domain logic | Python classes |
| Market data | `backend/app/providers/market_data` | normalized ticks/OHLC/candles | `MarketDataProvider` |
| Broker | `backend/app/providers/broker` | order/position/account ops | `BrokerAdapter` |
| AI | `backend/app/providers/ai` | LLM/embedding access, model registry | `AIProvider` |
| WS | `backend/app/ws` | connection manager, channel auth, broadcasting | JSON events |
| Trading engine | `backend/app/services/trading` | order lifecycle, positions, SL/TP | `TradingEngine` |
| Risk engine | `backend/app/services/risk` | position size, exposure, rule checks | `RiskEngine` |
| Strategy engine | `backend/app/services/strategy` | lifecycle hooks, indicator access | `Strategy` ABC |
| Backtest engine | `backend/app/services/backtest` | candle/tick replay, fills, metrics | `Backtester` |
| Market structure | `backend/app/services/analysis` | BOS/CHoCH, FVG, OB, liquidity, SMC | detectors |
| AI layer | `backend/app/services/ai` | feature pipeline → analysis → explanation | — |

## 3. Provider abstractions

All providers are registered in an app-level registry (dependency injection) and selected
via configuration. Nothing in the domain layer imports a concrete provider.

### 3.1 Market data

```python
class MarketDataProvider(ABC):
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def get_symbols(self) -> list[SymbolSpec]: ...
    def get_ticks(self, symbol, since) -> list[Tick]: ...
    def get_historical_data(self, symbol, timeframe, limit) -> list[Candle]: ...
    def subscribe(self, symbol, callback) -> str: ...   # returns subscription id
    def unsubscribe(self, subscription_id) -> None: ...
```

Normalized internal format: `SymbolSpec`, `Tick{ts, bid, ask, volume}`, `Candle{ts, o, h, l, c, v}`.
Adapters exist for any source (simulated generator, OANDA, Polygon, Yahoo, etc.). Phase 2 ships
a deterministic simulated provider so the app works offline.

### 3.2 Broker

```python
class BrokerAdapter(ABC):
    def connect(self, credentials) -> None: ...
    def disconnect(self) -> None: ...
    def authenticate(self) -> Account: ...
    def get_account(self) -> Account: ...
    def get_symbols(self) -> list[SymbolSpec]: ...
    def get_positions(self) -> list[Position]: ...
    def get_orders(self) -> list[Order]: ...
    def place_order(self, request: OrderRequest) -> Order: ...
    def modify_order(self, order_id, params) -> Order: ...
    def cancel_order(self, order_id) -> Order: ...
    def close_position(self, position_id) -> Position: ...
```

Phase 2 ships `PaperBroker`, a full simulation engine that executes against live market data
with configurable spread/slippage/commission and a virtual account. PAPER and LIVE are strict
separate environments (explicit flag, distinct account records, no cross-over).

### 3.3 AI

```python
class AIProvider(ABC):
    def generate(self, prompt, context) -> AIResult: ...
    def stream(self, prompt, context) -> Iterator[str]: ...
    def analyze(self, structured_analysis: MarketAnalysis) -> AIResult: ...
    def embed(self, text) -> list[float]: ...
    def health_check(self) -> ProviderStatus: ...
```

Phase 7 ships `OllamaProvider` (and later `LlamaCppProvider`, `HuggingFaceProvider`). Models
are user-selectable from the locally installed set. If no provider is healthy, the UI shows
"AI unavailable" — no paid API is ever called.

## 4. Real-time event contract

The WebSocket hub multiplexes channels per authenticated user/session. Events are versioned
JSON envelopes (`docs/EVENT_CONTRACTS.md`):

```
{ "type": "market.tick", "channel": "XAUUSD", "data": { ... }, "ts": 1720... }
```

Channels: `market.<symbol>`, `candles.<symbol>.<tf>`, `account.<id>`, `orders`, `positions`,
`alerts`, `ai.scanner`, `system.status`. Connection requires a JWT (query param or first message).

## 5. Security model

- Passwords: Argon2 (via `argon2-cffi`), never stored in plain text.
- Sessions: short-lived JWT access tokens + rotating refresh tokens (hashed at rest).
- Broker credentials: encrypted at rest (Fernet) with a key from env/secret store; never logged.
- Audit log: every auth, trade, settings, and AI-execution action is recorded.
- Rate limiting on auth endpoints; input validation on every route.
- AI execution: disabled by default; requires explicit opt-in + risk limits + paper validation
  + a live confirmation + a kill switch, and every decision/execution is logged.

## 6. Database

MariaDB in production; SQLite for local dev/tests. Schema defined in
`docs/DATABASE_SCHEMA.md`, managed with Alembic migrations. Tables: users, accounts, brokers,
symbols, market_data_meta, orders, positions, trades, strategies, backtests, chart_layouts,
drawings, ai_analyses, ai_conversations, journal_entries, alerts, audit_logs.

## 7. Frontend architecture

- `lib/core/` — config, REST API client, WebSocket client, lightweight state stores
  (auth, connection, workspace, market, trading).
- `lib/features/shell/` — TopBar, Workspace (dock/resize/collapse/rearrange), Panel primitives.
- `lib/features/panels/` — MarketWatch, Chart, AI Copilot, Trading Terminal (tabs: Positions,
  Orders, History, Account, Journal, Alerts, Experts, Logs).
- Workspace layouts persist to the backend (`chart_layouts` table) and restore on login.
- Charting uses a custom `CustomPainter` Canvas engine (Phase 3) for large datasets.
- UI theme: professional terminal visual language, dark/light, dense, keyboard-driven,
  command palette.

## 8. Backtesting & strategies

Strategies implement a lifecycle ABC (`initialize/on_tick/on_candle/on_signal/on_order/
on_position/shutdown`) and access only market data, indicators, account, positions, orders —
never UI. The backtester replays candles/ticks deterministically with spread/slippage/
commission/swap/SL/TP/trailing, and emits standard metrics (profit factor, max DD, Sharpe,
expectancy, equity curve). AI strategy builder compiles natural language → structured rules
that can be backtested; deployment to live requires explicit confirmation.

## 9. Observability

Structured JSON logging, request IDs, connection/broker/AI/market-data status surfaces
(`/health`, WS `system.status`), and performance counters for chart/backtest/AI work.
See `docs/ROADMAP.md` for phased delivery order.
