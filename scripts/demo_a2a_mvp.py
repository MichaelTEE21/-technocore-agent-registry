#!/usr/bin/env python3
"""Local A2A Communication MVP demo (TestClient — no remote HTTP to agents).

Usage (from repo root):
  PYTHONPATH=src python scripts/demo_a2a_mvp.py

Disclaimer: Not official FLOP. Registry-mediated only. No private keys stored.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "10000")
os.environ["REGISTRY_TOKEN"] = ""

DEMO_DESCRIPTION = "Analyse the tokenomics of Project X."
DEMO_RESULT = {
    "summary": "Placeholder tokenomics analysis for Project X (demo).",
    "token_supply": "1_000_000_000",
    "allocation": "Team 20% · Community 40% · Treasury 40%",
    "vesting": "24-month linear with 6-month cliff",
}

KNOWN_DID = "did:key:z6Mkrv5ZL3VsapUdVKirgFiJVdw7y5w8Bq3zDvmfNMDSAAep"


def main() -> int:
    from fastapi.testclient import TestClient

    from tar import config as cfg
    from tar import db as dbmod
    from tar import main as mainmod

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp.name}"
    settings = cfg.load_settings()
    cfg.settings = settings
    dbmod.reset_engine(settings.database_url)
    app = mainmod.create_app()

    with TestClient(app) as client:
        print("== Register Agent A (mananze-technocore-agent, did:key) ==")
        a = client.post(
            "/agents",
            json={
                "id": "mananze-technocore-agent",
                "name": "Mananze Technocore Agent",
                "did": KNOWN_DID,
                "capabilities": [
                    {"id": "crypto-research", "category": "crypto-web3", "level": "advanced"},
                ],
                "protocols": ["http", "a2a"],
                "status": "online",
                "endpoint": "https://example.invalid/agents/mananze",
            },
        )
        print(a.status_code, a.json().get("public_key", "")[:16] + "…")

        print("== Register Agent B (tokenomics-analysis) ==")
        b = client.post(
            "/agents",
            json={
                "id": "a2a-tokenomics-worker",
                "name": "Tokenomics Worker B",
                "did": "did:example:a2a-tokenomics-worker",
                "capabilities": [
                    {
                        "id": "tokenomics-analysis",
                        "category": "crypto-web3",
                        "level": "advanced",
                    }
                ],
                "protocols": ["http", "a2a"],
                "status": "online",
                "fictional": True,
            },
        )
        print(b.status_code, b.json()["id"])

        print("== Discover by capability ==")
        d = client.get("/discover", params={"capability": "tokenomics-analysis"})
        print(d.status_code, [i["agent"]["id"] for i in d.json()["items"]])

        print("== Create directed task A→B ==")
        t = client.post(
            "/tasks",
            json={
                "requester": "mananze-technocore-agent",
                "target_agent_id": "a2a-tokenomics-worker",
                "requested_capability": "tokenomics-analysis",
                "description": DEMO_DESCRIPTION,
            },
        )
        task = t.json()
        print(t.status_code, task["task_id"], task["status"])
        tid = task["task_id"]

        print("== ACCEPT as B ==")
        acc = client.post(f"/tasks/{tid}/accept", json={"agent_id": "a2a-tokenomics-worker"})
        print(acc.status_code, acc.json()["status"], "accepted_at=", acc.json().get("accepted_at"))

        print("== SUBMIT (alias) result as B ==")
        sub = client.post(
            f"/tasks/{tid}/submit",
            json={"agent_id": "a2a-tokenomics-worker", "result": DEMO_RESULT},
        )
        print(sub.status_code, sub.json()["status"], "completed_at=", sub.json().get("completed_at"))

        print("== GET task as A (sees result) ==")
        got = client.get(f"/tasks/{tid}")
        print(got.status_code, json.dumps(got.json()["result"], indent=2))

        print("== History ==")
        hist = client.get(f"/tasks/{tid}/history")
        print(
            hist.status_code,
            "events=",
            [e["event"] for e in hist.json()["events"]],
            "messages=",
            [m["type"] for m in hist.json()["messages"]],
        )

        print("== UI communicate ==")
        ui = client.get(
            "/ui/communicate",
            params={
                "requester": "mananze-technocore-agent",
                "assignee": "a2a-tokenomics-worker",
                "capability": "tokenomics-analysis",
                "task_id": tid,
            },
        )
        print(ui.status_code, "bytes=", len(ui.content))
        print("Done. Not official FLOP. Registry-mediated MVP only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
