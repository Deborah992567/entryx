FROM python:3.12-slim AS base

RUN groupadd -r entryx && useradd -r -g entryx -d /app -s /sbin/nologin entryx

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml backend/README.md backend/
WORKDIR /app/backend
RUN pip install --no-cache-dir -e .

COPY backend/ .

RUN chown -R entryx:entryx /app
USER entryx

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
