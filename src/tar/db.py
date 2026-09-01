"""Session factory. SQLite for local demo; swap DATABASE_URL for Postgres."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from tar.config import settings
from tar.models import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def make_engine(database_url: str | None = None) -> Engine:
    url = database_url or settings.database_url
    kwargs: dict = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # Postgres-ready: queue_pool + pre_ping. Caller supplies postgresql+psycopg://...
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
    return create_engine(url, **kwargs)


def make_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    eng = engine or get_engine()
    return sessionmaker(bind=eng, autoflush=False, autocommit=False, expire_on_commit=False)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = make_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = make_session_factory(get_engine())
    return _SessionLocal


def init_db(engine: Engine | None = None) -> None:
    eng = engine or get_engine()
    Base.metadata.create_all(bind=eng)


def reset_engine(database_url: str) -> Engine:
    """Used by tests to point at a temp SQLite file."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = make_engine(database_url)
    _SessionLocal = make_session_factory(_engine)
    init_db(_engine)
    return _engine


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
