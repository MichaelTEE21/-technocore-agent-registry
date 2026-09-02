"""Session factory. SQLite for local demo; swap DATABASE_URL for Postgres."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from tar.config import ConfigurationError, is_serverless, settings
from tar.models import Base, Capability
from tar.taxonomy import list_capabilities

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _ensure_sqlite_parent(url: str) -> None:
    """Create parent dir for local SQLite files only (no-op for Postgres)."""
    if not url.startswith("sqlite:///"):
        return
    db_path = Path(url.removeprefix("sqlite:///"))
    if str(db_path) in ("", ":memory:") or str(db_path).startswith(":memory:"):
        return
    db_path.parent.mkdir(parents=True, exist_ok=True)


def make_engine(database_url: str | None = None) -> Engine:
    from sqlalchemy import create_engine

    url = database_url or settings.database_url
    if url.startswith("sqlite") and is_serverless():
        raise ConfigurationError(
            "SQLite cannot be used on serverless/Vercel. Set DATABASE_URL to "
            "hosted Postgres (e.g. Neon) in the project environment."
        )
    if url.startswith("sqlite"):
        _ensure_sqlite_parent(url)
    kwargs: dict = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
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


def _add_missing_columns(engine: Engine) -> None:
    """Lightweight migrate: ADD COLUMN for new fields on existing SQLite files."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    wanted = {
        "agents": [("public_key", "VARCHAR(128)")],
        "agent_capabilities": [("evidence_status", "VARCHAR(32) DEFAULT 'claimed'")],
        "verification_records": [
            ("capability_id", "VARCHAR(128)"),
            ("checker_id", "VARCHAR(128)"),
        ],
        "swarm_members": [("role", "VARCHAR(32) DEFAULT 'recommended'")],
        # Portable TIMESTAMP (SQLite + Postgres/Neon); not SQLite-only SQL.
        "tasks": [
            ("accepted_at", "TIMESTAMP"),
            ("completed_at", "TIMESTAMP"),
        ],
    }
    with engine.begin() as conn:
        for table, cols in wanted.items():
            if table not in tables:
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, decl in cols:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {decl}"))


def sync_taxonomy(session: Session) -> None:
    for cap in list_capabilities():
        row = session.get(Capability, cap["id"])
        if row is None:
            session.add(
                Capability(
                    id=cap["id"],
                    name=cap["name"],
                    category=cap["category"],
                    description=cap.get("description") or "",
                    disclaimer=cap.get("disclaimer"),
                )
            )
        else:
            row.name = cap["name"]
            row.category = cap["category"]
            row.description = cap.get("description") or ""
            row.disclaimer = cap.get("disclaimer")
    session.commit()


def init_db(engine: Engine | None = None) -> None:
    eng = engine or get_engine()
    Base.metadata.create_all(bind=eng)
    _add_missing_columns(eng)
    db = make_session_factory(eng)()
    try:
        sync_taxonomy(db)
    finally:
        db.close()


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
