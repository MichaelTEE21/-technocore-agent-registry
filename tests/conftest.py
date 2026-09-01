from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "10000")
os.environ.setdefault("MAX_REQUEST_BYTES", "65536")
os.environ["REGISTRY_TOKEN"] = ""  # open demo in tests unless a test overrides


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("REGISTRY_TOKEN", "")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "10000")
    from tar import config as cfg
    from tar import db as dbmod
    from tar import main as mainmod

    settings = cfg.load_settings()
    monkeypatch.setattr(cfg, "settings", settings)
    dbmod.reset_engine(settings.database_url)
    app = mainmod.create_app()
    app.state.settings = settings
    with TestClient(app) as tc:
        yield tc


def sample_agent(suffix: str, caps: list[dict], status: str = "online") -> dict:
    return {
        "id": f"test-{suffix}",
        "name": f"{suffix.title()} Agent",
        "did": f"did:example:test-{suffix}",
        "version": "0.1.0",
        "description": f"FICTIONAL test agent {suffix}. Not a real service.",
        "capabilities": caps,
        "protocols": ["http"],
        "status": status,
        "endpoint": f"https://example.invalid/agents/{suffix}",
        "verification": {"status": "claimed"},
        "fictional": True,
    }


AGENT_A = sample_agent(
    "research",
    [
        {"id": "crypto-research", "category": "crypto-web3", "level": "advanced"},
        {"id": "web-research", "category": "research", "level": "advanced"},
        {"id": "source-verification", "category": "research", "level": "intermediate"},
    ],
)
AGENT_B = sample_agent(
    "document",
    [
        {"id": "pdf-analysis", "category": "documents", "level": "advanced"},
        {"id": "document-extraction", "category": "documents", "level": "advanced"},
        {"id": "summarization", "category": "documents", "level": "intermediate"},
    ],
)
AGENT_C = sample_agent(
    "developer",
    [
        {"id": "python", "category": "software", "level": "advanced"},
        {"id": "api-development", "category": "software", "level": "advanced"},
        {"id": "testing", "category": "software", "level": "intermediate"},
    ],
    status="unknown",
)
