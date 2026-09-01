#!/usr/bin/env python3
"""Acceptance flow: register A B C, query capabilities, search, profile, DID/caps/verification.

Uses an in-process TestClient so a separately started server is not required.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ["RATE_LIMIT_PER_MINUTE"] = "10000"
os.environ["REGISTRY_TOKEN"] = ""


def main() -> int:
    from fastapi.testclient import TestClient

    from tar import config as cfg
    from tar import db as dbmod
    from tar import main as mainmod

    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_file.close()
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file.name}"
    settings = cfg.load_settings()
    cfg.settings = settings
    dbmod.reset_engine(settings.database_url)
    app = mainmod.create_app()
    app.state.settings = settings

    a = json.loads((ROOT / "examples" / "example-agent.json").read_text(encoding="utf-8"))
    b = {
        "id": "test-document",
        "name": "Document Agent",
        "did": "did:example:test-document",
        "version": "0.1.0",
        "description": "FICTIONAL test agent: pdf-analysis, document-extraction, summarization.",
        "capabilities": [
            {"id": "pdf-analysis", "category": "documents", "level": "advanced"},
            {"id": "document-extraction", "category": "documents", "level": "advanced"},
            {"id": "summarization", "category": "documents", "level": "intermediate"},
        ],
        "status": "online",
        "endpoint": "https://example.invalid/agents/document",
        "protocols": ["http"],
    }
    c = {
        "id": "test-developer",
        "name": "Developer Agent",
        "did": "did:example:test-developer",
        "version": "0.1.0",
        "description": "FICTIONAL test agent: python, api-development, testing.",
        "capabilities": [
            {"id": "python", "category": "software", "level": "advanced"},
            {"id": "api-development", "category": "software", "level": "advanced"},
            {"id": "testing", "category": "software", "level": "intermediate"},
        ],
        "status": "unknown",
        "endpoint": "https://example.invalid/agents/developer",
        "protocols": ["http"],
    }

    with TestClient(app) as client:
        for payload in (a, b, c):
            resp = client.post("/agents", json=payload)
            assert resp.status_code == 201, resp.text
            print(f"registered {payload['id']}")

        caps = client.get("/capabilities")
        assert caps.status_code == 200
        print(f"capabilities count={caps.json()['count']}")

        search = client.get("/agents", params={"capability": "crypto-research"})
        assert search.status_code == 200
        assert search.json()["count"] >= 1
        print("search crypto-research:", [i["id"] for i in search.json()["items"]])

        profile = client.get("/agents/test-research")
        assert profile.status_code == 200
        agent = profile.json()
        print("profile did=", agent["did"])
        print("profile caps=", [c["id"] for c in agent["capabilities"]])
        print("profile verification=", agent["verification"]["status"])

        ver = client.get("/agents/test-research/verification")
        assert ver.status_code == 200
        print("verification records=", len(ver.json()["items"]))

        swarm = client.get("/swarms/assemble", params={"capability": "crypto-research"})
        assert swarm.status_code == 200
        print("proposed swarm members=", swarm.json()["member_agent_ids"])

    print("demo_flow: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
