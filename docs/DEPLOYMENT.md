# EntryX Deployment Guide

## Prerequisites

- Python 3.12+
- Flutter 3.x (for desktop frontend)
- Ollama (for local AI features)
- MariaDB or SQLite (dev fallback)

## Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # edit as needed
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Frontend Setup

```bash
cd frontend
flutter pub get
flutter run -d macos   # or linux/windows
```

## AI Setup (Optional)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull qwen2.5:1.5b

# Verify
ollama list
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | EntryX | Application name |
| `SECRET_KEY` | (auto) | JWT signing key |
| `DATABASE_URL` | sqlite:///entryx.db | Database connection |
| `AI_PROVIDER` | ollama | AI backend |
| `AI_OLLAMA_URL` | http://localhost:11434 | Ollama endpoint |
| `AI_DEFAULT_MODEL` | qwen2.5:1.5b | Default model |

## Production Deployment

1. Set `SECRET_KEY` to a strong random value
2. Use MariaDB instead of SQLite
3. Set `APP_ENV=production`
4. Run behind a reverse proxy (nginx/caddy)
5. Enable HTTPS
6. Run Ollama as a systemd service

## Desktop Packaging

EntryX uses Flutter for desktop. Build release bundles:

```bash
cd frontend
flutter build macos    # macOS .app
flutter build linux    # Linux AppImage
flutter build windows  # Windows installer
```

## Architecture

```
entryx/
  backend/          Python/FastAPI REST API + WebSocket
  frontend/         Flutter desktop application
  docs/             Architecture, roadmap, contracts
```

### Backend Structure

```
backend/app/
  api/v1/           REST endpoints (auth, market, trading, AI, etc.)
  core/             Config, security, logging, exceptions
  db/               SQLAlchemy models + Alembic migrations
  providers/        AI (Ollama), broker adapters, market data
  schemas/          Pydantic request/response models
  services/         Business logic (broker, backtest, SMC, AI, etc.)
  ws/               WebSocket hub + manager
```

### Frontend Structure

```
frontend/lib/
  app/              Theme, app entry point
  core/             API client, WebSocket client, config, models
  features/
    chart/          Canvas chart engine, painter, geometry, store
    panels/         UI panels (chart, market watch, AI copilot, trading)
    shell/          App shell, workspace dock system
    backtest/       Backtest models
    market/         Market watch store
```
