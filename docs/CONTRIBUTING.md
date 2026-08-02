# EntryX Contributing

## Development workflow

1. Work in vertical slices (see `docs/ROADMAP.md`).
2. Run the app + tests after each phase; fix before moving on.
3. Commit each logical unit with a concise message; push to `main`.
4. Update `docs/` when behavior or contracts change.

## Running locally

### Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # adjust DATABASE_URL
alembic upgrade head
uvicorn app.main:app --reload   # http://localhost:8000
pytest                          # run tests
ruff check .
```

DB defaults: SQLite (`sqlite:///./entryx.db`) for local dev; set `DATABASE_URL` to
MariaDB for production:
`mysql+pymysql://user:pass@localhost:3306/entryx?charset=utf8mb4`.

### Frontend (Flutter)
```bash
cd frontend
flutter pub get
flutter run -d macos             # desktop app
flutter test                     # run tests
flutter analyze
```

The Flutter app targets `http://localhost:8000` by default (configurable in
`lib/core/config.dart`).

### AI
Requires a local provider (default Ollama on `http://localhost:11434`). Pull a small model:
```bash
ollama pull qwen2.5:1.5b
```
`GET /api/v1/ai/status` reports provider health and available models. If none is reachable,
the UI shows "AI unavailable" — EntryX never falls back to a paid API.
