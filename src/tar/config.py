"""Runtime configuration. Secrets are never required for a local demo."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]


class ConfigurationError(RuntimeError):
    """Raised when runtime config is unsuitable for the current environment."""


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def is_serverless() -> bool:
    """True on Vercel or other common serverless hosts with a read-only FS."""
    if _env("VERCEL") == "1":
        return True
    if _env("VERCEL_ENV") is not None:
        return True
    # Typical serverless markers (fail closed when persistence is required).
    for name in (
        "AWS_LAMBDA_FUNCTION_NAME",
        "FUNCTIONS_WORKER_RUNTIME",
        "K_SERVICE",  # Cloud Run / Knative
        "NETLIFY",
    ):
        if _env(name) is not None:
            return True
    return False


def normalize_database_url(url: str) -> str:
    """Rewrite bare postgres:// / postgresql:// to SQLAlchemy + psycopg2.

    Neon/Vercel often inject postgres://… without a driver. Do not log the URL.
    """
    scheme = urlparse(url).scheme
    if scheme == "postgres":
        return "postgresql+psycopg2://" + url[len("postgres://") :]
    if scheme == "postgresql":
        return "postgresql+psycopg2://" + url[len("postgresql://") :]
    return url


def _is_sqlite_url(url: str) -> bool:
    return urlparse(url).scheme.startswith("sqlite")


def require_persistent_database(url: str) -> None:
    """On serverless, require a non-SQLite DATABASE_URL (hosted Postgres/Neon)."""
    if not is_serverless():
        return
    if not url or _is_sqlite_url(url):
        raise ConfigurationError(
            "Serverless/Vercel deployments require DATABASE_URL set to a hosted "
            "Postgres (e.g. Neon) connection string. SQLite is not supported on "
            "the read-only serverless filesystem — set DATABASE_URL in the Vercel "
            "project environment (do not use /tmp SQLite for production)."
        )


@dataclass(frozen=True)
class Settings:
    database_url: str
    registry_token: str | None
    max_request_bytes: int
    rate_limit_per_minute: int
    host: str
    port: int

    @property
    def auth_required(self) -> bool:
        return bool(self.registry_token)


def load_settings() -> Settings:
    raw = _env("DATABASE_URL")
    if raw is None:
        db = f"sqlite:///{ROOT / 'data' / 'registry.db'}"
    else:
        db = normalize_database_url(raw)
    require_persistent_database(db)
    return Settings(
        database_url=db,
        registry_token=_env("REGISTRY_TOKEN"),
        max_request_bytes=int(_env("MAX_REQUEST_BYTES", "65536") or "65536"),
        rate_limit_per_minute=int(_env("RATE_LIMIT_PER_MINUTE", "120") or "120"),
        host=_env("HOST", "127.0.0.1") or "127.0.0.1",
        port=int(_env("PORT", "8080") or "8080"),
    )


settings = load_settings()
