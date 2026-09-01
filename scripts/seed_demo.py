#!/usr/bin/env python3
"""Seed five FICTIONAL test agents and an example swarm.

Ed25519 private keys are written only to gitignored data/keys/*.key files.
They are never printed, logged, or stored in the registry database.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tar.crypto import generate_keypair, public_key_hex  # noqa: E402
from tar.db import get_session_factory, init_db  # noqa: E402
from tar.demo import AGENTS  # noqa: E402
from tar.models import (  # noqa: E402
    Agent,
    AgentCapability,
    Swarm,
    SwarmMember,
    VerificationRecord,
)

KEY_DIR = ROOT / "data" / "keys"


def _ensure_keys(agent_id: str) -> str:
    KEY_DIR.mkdir(parents=True, exist_ok=True)
    path = KEY_DIR / f"{agent_id}.key"
    if path.exists():
        raw = path.read_bytes()
        if len(raw) == 64:
            raw = bytes.fromhex(raw.decode().strip())
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as EK

        pub = EK.from_private_bytes(raw).public_key().public_bytes_raw()
        return public_key_hex(pub)
    priv, pub = generate_keypair()
    path.write_bytes(priv)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    return public_key_hex(pub)


def seed() -> None:
    init_db()
    db = get_session_factory()()
    try:
        ids = []
        for spec in AGENTS:
            ids.append(spec["id"])
            if db.get(Agent, spec["id"]) is not None:
                continue
            pub = _ensure_keys(spec["id"])
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
                public_key=pub,
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
                        evidence_status="claimed",
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
                        "Example swarm of FICTIONAL test agents grouped by complementary "
                        "capabilities. Local only. Not a live network."
                    ),
                    required_capabilities_json=json.dumps(
                        ["crypto-research", "pdf-analysis", "python", "legal-research", "security-analysis"]
                    ),
                )
            )
            db.flush()
            for agent_id in ids:
                db.add(SwarmMember(swarm_id="demo-core", agent_id=agent_id, role="recommended"))
        db.commit()
        print("Seeded fictional demo agents:", ", ".join(ids))
        print("Seeded example swarm: demo-core")
        print("Private keys (if generated) live in data/keys/ — gitignored, never printed.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
