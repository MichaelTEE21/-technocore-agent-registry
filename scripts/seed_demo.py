#!/usr/bin/env python3
"""Seed three FICTIONAL test agents and an example swarm. Never logs secrets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tar.db import get_session_factory, init_db  # noqa: E402
from tar.models import Agent, AgentCapability, Swarm, SwarmMember, VerificationRecord  # noqa: E402

FICTIONAL = "FICTIONAL test agent for the Technocore Agent Registry demo. Not a real service."

AGENTS = [
    {
        "id": "test-research",
        "name": "Research Agent",
        "did": "did:example:test-research",
        "version": "0.1.0",
        "description": (
            f"{FICTIONAL} Advertises crypto-research, web-research, and source-verification."
        ),
        "status": "online",
        "endpoint": "https://example.invalid/agents/research",
        "protocols": ["http"],
        "capabilities": [
            {"id": "crypto-research", "category": "crypto-web3", "level": "advanced"},
            {"id": "web-research", "category": "research", "level": "advanced"},
            {"id": "source-verification", "category": "research", "level": "intermediate"},
        ],
    },
    {
        "id": "test-document",
        "name": "Document Agent",
        "did": "did:example:test-document",
        "version": "0.1.0",
        "description": (
            f"{FICTIONAL} Advertises pdf-analysis, document-extraction, and summarization."
        ),
        "status": "online",
        "endpoint": "https://example.invalid/agents/document",
        "protocols": ["http"],
        "capabilities": [
            {"id": "pdf-analysis", "category": "documents", "level": "advanced"},
            {"id": "document-extraction", "category": "documents", "level": "advanced"},
            {"id": "summarization", "category": "documents", "level": "intermediate"},
        ],
    },
    {
        "id": "test-developer",
        "name": "Developer Agent",
        "did": "did:example:test-developer",
        "version": "0.1.0",
        "description": f"{FICTIONAL} Advertises python, api-development, and testing.",
        "status": "unknown",
        "endpoint": "https://example.invalid/agents/developer",
        "protocols": ["http"],
        "capabilities": [
            {"id": "python", "category": "software", "level": "advanced"},
            {"id": "api-development", "category": "software", "level": "advanced"},
            {"id": "testing", "category": "software", "level": "intermediate"},
        ],
    },
]


def seed() -> None:
    init_db()
    db = get_session_factory()()
    try:
        for spec in AGENTS:
            if db.get(Agent, spec["id"]) is not None:
                continue
            agent = Agent(
                id=spec["id"],
                name=spec["name"],
                did=spec["did"],
                version=spec["version"],
                description=spec["description"],
                protocols_json=json.dumps(spec["protocols"]),
                status=spec["status"],
                endpoint=spec["endpoint"],
                verification_status="claimed",
                fictional="true",
            )
            db.add(agent)
            db.flush()
            for cap in spec["capabilities"]:
                db.add(
                    AgentCapability(
                        agent_id=agent.id,
                        capability_id=cap["id"],
                        category=cap["category"],
                        level=cap["level"],
                    )
                )
            db.add(
                VerificationRecord(
                    agent_id=agent.id,
                    kind="claim",
                    status="claimed",
                    summary="Seeded fictional profile; not verified.",
                )
            )
        if db.get(Swarm, "demo-core") is None:
            db.add(
                Swarm(
                    id="demo-core",
                    name="Demo Core Swarm",
                    description=(
                        "Example swarm of the three FICTIONAL test agents. "
                        "Grouped by complementary capabilities. Not a live network."
                    ),
                    required_capabilities_json=json.dumps(
                        ["crypto-research", "pdf-analysis", "python"]
                    ),
                )
            )
            db.flush()
            for agent_id in ("test-research", "test-document", "test-developer"):
                db.add(SwarmMember(swarm_id="demo-core", agent_id=agent_id))
        db.commit()
        print("Seeded fictional agents: test-research, test-document, test-developer")
        print("Seeded example swarm: demo-core")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
