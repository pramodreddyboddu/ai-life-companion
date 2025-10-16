"""Database session utilities."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.settings import settings


engine = create_engine(settings.database.url, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def get_session() -> Iterator[Session]:
    """Yield a database session for request scope."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
