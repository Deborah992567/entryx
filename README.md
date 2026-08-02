# ENTRYX

A professional, MetaTrader-style trading terminal with a deeply integrated local-AI layer.

EntryX is built as a serious software product — not a demo. It combines professional
trading-terminal functionality, real-time market data, advanced charting, order/position
management, strategy development, backtesting, and a local-first AI Copilot that
understands the market structure behind the chart.

## Core principles

- **Local-first AI.** All AI features run on free/open-source or self-hosted models
  (Ollama, llama.cpp, Hugging Face). No paid API is required, and none is ever called
  silently. If a local model is unavailable, EntryX reports "AI unavailable".
- **Modular architecture.** Frontend, backend, market-data engine, trading engine,
  broker adapters, chart engine, strategy/backtest engines, indicator engine, AI engine,
  risk engine, auth, database, notifications, logging, configuration are separated by
  clear interfaces.
- **Provider abstraction.** Market data, brokers, and AI models are all adapter-based.
  EntryX never hard-codes a single provider or broker.
- **AI never controls real trading by default.** AI analysis and execution are separated.
  Execution always passes through the Strategy → Risk → Execution → Broker chain with
  explicit user opt-in, validation, and a kill switch.

## Repo layout

```
entryx/
├── docs/           # Architecture, roadmap, API/event/database contracts, testing strategy
├── backend/        # Python/FastAPI service (auth, DB, market data, trading, risk, strategy, AI)
│   ├── app/
│   │   ├── core/       # config, security, logging, exceptions
│   │   ├── db/         # SQLAlchemy models + session
│   │   ├── api/v1/     # REST routers
│   │   ├── schemas/    # Pydantic contracts
│   │   ├── services/   # business logic
│   │   ├── providers/  # market_data/, broker/, ai/ adapters
│   │   └── ws/         # WebSocket hub
│   └── tests/
├── frontend/       # Flutter desktop app (macOS/Windows/Linux)
│   └── lib/
│       ├── app/         # app shell, routing, theme
│       ├── core/        # config, API client, WS client, state stores
│       ├── features/    # auth, shell, market_watch, chart, ai, trading
└── .github/        # CI
```

## Stack

- Backend: Python 3.14, FastAPI, SQLAlchemy 2, Alembic, WebSockets
- Database: MariaDB (production), SQLite (dev/tests)
- Frontend: Flutter 3.41 (Dart 3.11) — desktop-first trading terminal UI
- AI: Ollama / llama.cpp / Hugging Face open models, via a pluggable `AIProvider` interface
- Data/state: normalized internal market-data format; provider adapters for any source

## Development status

Phase 1 (architecture, auth, database, desktop shell, workspace system) is the current focus.
See [docs/ROADMAP.md](docs/ROADMAP.md) for the phased build order and status.
