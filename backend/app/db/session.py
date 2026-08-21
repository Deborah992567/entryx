"""Database engine and session factory.

Production uses MariaDB (mysql+pymysql). Tests and local dev default to SQLite
via DATABASE_URL. Session management is dependency-injected in app.api.deps.
"""

from __future__ import annotations

from collections.abc import Generator

from app.core.config import get_settings
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

settings = get_settings()

_pool_kwargs: dict = {"pool_pre_ping": True}
if not settings.is_sqlite:
    _pool_kwargs.update({"pool_size": 10, "max_overflow": 20, "pool_recycle": 3600})

engine = create_engine(
    settings.database_url,
    echo=False,
    **_pool_kwargs,
    connect_args=settings.database_connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
