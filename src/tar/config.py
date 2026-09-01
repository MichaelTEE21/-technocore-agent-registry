"""Runtime configuration. Secrets are never required for a local demo."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


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
    db = _env("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'registry.db'}")
    assert db is not None
    return Settings(
        database_url=db,
        registry_token=_env("REGISTRY_TOKEN"),
        max_request_bytes=int(_env("MAX_REQUEST_BYTES", "65536") or "65536"),
        rate_limit_per_minute=int(_env("RATE_LIMIT_PER_MINUTE", "120") or "120"),
        host=_env("HOST", "127.0.0.1") or "127.0.0.1",
        port=int(_env("PORT", "8080") or "8080"),
    )


settings = load_settings()
