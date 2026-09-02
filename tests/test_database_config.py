"""Unit tests for serverless DB config: SQLite local, Postgres required on Vercel."""

from __future__ import annotations

import pytest

from tar.config import (
    ConfigurationError,
    is_serverless,
    load_settings,
    normalize_database_url,
    require_persistent_database,
)


def test_local_default_remains_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("VERCEL_ENV", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    monkeypatch.delenv("FUNCTIONS_WORKER_RUNTIME", raising=False)
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.delenv("NETLIFY", raising=False)
    settings = load_settings()
    assert settings.database_url.startswith("sqlite:///")
    assert settings.database_url.endswith("registry.db")
    assert not is_serverless()


@pytest.mark.parametrize(
    "raw,expected_prefix",
    [
        ("postgres://user:pass@host/db", "postgresql+psycopg2://"),
        ("postgresql://user:pass@host/db", "postgresql+psycopg2://"),
        ("postgresql+psycopg2://user:pass@host/db", "postgresql+psycopg2://"),
    ],
)
def test_postgres_url_normalizes(raw, expected_prefix):
    out = normalize_database_url(raw)
    assert out.startswith(expected_prefix)
    assert "user:pass@host/db" in out
    # Already-driver URLs must not double-prefix.
    if raw.startswith("postgresql+"):
        assert out == raw


def test_vercel_without_database_url_raises(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ConfigurationError, match="DATABASE_URL"):
        load_settings()


def test_vercel_with_sqlite_database_url_raises(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/registry.db")
    with pytest.raises(ConfigurationError, match="Postgres|DATABASE_URL|SQLite"):
        load_settings()


def test_vercel_with_postgresql_url_loads(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgres://user:secret@ep-example.neon.tech/neondb?sslmode=require",
    )
    settings = load_settings()
    assert settings.database_url.startswith("postgresql+psycopg2://")
    assert "ep-example.neon.tech" in settings.database_url
    assert is_serverless()
    # require_persistent_database accepts non-sqlite
    require_persistent_database(settings.database_url)


def test_vercel_env_marker_alone_is_serverless(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("VERCEL_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    assert is_serverless()
    settings = load_settings()
    assert settings.database_url.startswith("postgresql+psycopg2://")


def test_make_engine_refuses_sqlite_on_serverless(monkeypatch, tmp_path):
    monkeypatch.setenv("VERCEL", "1")
    from tar import db as dbmod
    from tar.config import ConfigurationError as CE

    with pytest.raises(CE, match="SQLite"):
        dbmod.make_engine(f"sqlite:///{tmp_path / 'x.db'}")


def test_make_engine_creates_sqlite_parent_locally(monkeypatch, tmp_path):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("VERCEL_ENV", raising=False)
    nested = tmp_path / "nested" / "dir" / "test.db"
    assert not nested.parent.exists()
    from tar import db as dbmod

    engine = dbmod.make_engine(f"sqlite:///{nested}")
    assert nested.parent.is_dir()
    engine.dispose()
