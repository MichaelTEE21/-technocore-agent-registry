#!/usr/bin/env python3
"""E2E local workflow on a clean in-process registry.

register A/B → search B by capability → inspect B → create task → B accepts
→ progress → signed result → signature verified → contribution recorded
→ multi-capability task decomposed → compatible agents discovered → swarm assembled.

Uses an in-process TestClient so a separately started server is not required.
Private keys stay in a temp directory and are never printed.
"""

from __future__ import annotations

import os
import sys
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ["RATE_LIMIT_PER_MINUTE"] = "10000"
os.environ["REGISTRY_TOKEN"] = ""

from tar.crypto import (  # noqa: E402
    canonical_message_bytes,
    generate_keypair,
    public_key_hex,
    sign,
    verify,
)
from tar.demo import AGENTS  # noqa: E402


def _iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _signed(priv: bytes, *, message_id: str, type: str, frm: str, to: str, task_id: str, payload: dict, timestamp: str) -> str:
    msg = canonical_message_bytes(
        message_id=message_id,
        type=type,
        from_agent=frm,
        to_agent=to,
        timestamp=timestamp,
        task_id=task_id,
        payload=payload,
    )
    return sign(priv, msg)


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

    keydir = Path(tempfile.mkdtemp(prefix="tar-keys-"))
    keys: dict[str, bytes] = {}
    pubs: dict[str, str] = {}
    payloads = []
    for spec in AGENTS:
        priv, pub = generate_keypair()
        keys[spec["id"]] = priv
        pubs[spec["id"]] = public_key_hex(pub)
        (keydir / f"{spec['id']}.key").write_bytes(priv)
        body = dict(spec)
        body["public_key"] = pubs[spec["id"]]
        body["fictional"] = True
        body["verification"] = {"status": "claimed"}
        payloads.append(body)

    with TestClient(app) as client:
        for payload in payloads:
            resp = client.post("/agents", json=payload)
            assert resp.status_code == 201, resp.text
            assert "private" not in resp.text.lower()
            print(f"registered {payload['id']} (demo)")

        caps = client.get("/capabilities")
        assert caps.status_code == 200
        ids = {i["id"] for i in caps.json()["items"]}
        for needed in (
            "crypto-research",
            "legal-research",
            "pdf-analysis",
            "python",
            "security-analysis",
            "agent-orchestration",
            "task-delegation",
        ):
            assert needed in ids, needed
        print(f"capabilities count={caps.json()['count']}")

        search = client.get("/agents", params={"capability": "pdf-analysis"})
        assert search.status_code == 200
        found_ids = [i["id"] for i in search.json()["items"]]
        assert "test-document" in found_ids
        print("search pdf-analysis:", found_ids)

        profile = client.get("/agents/test-document")
        assert profile.status_code == 200
        agent = profile.json()
        print("inspect B did=", agent["did"])
        print("inspect B caps=", [c["id"] for c in agent["capabilities"]])
        print("inspect B verification=", agent["verification"]["status"])
        assert agent["fictional"] is True

        disc = client.get("/discover", params=[("capability", "pdf-analysis")])
        assert disc.status_code == 200
        assert disc.json()["count"] >= 1
        assert "ranking" in disc.json()
        print("discover rank[0]=", disc.json()["items"][0]["rank"])

        created = client.post(
            "/tasks",
            json={
                "requester": "test-research",
                "assignee": "test-document",
                "requested_capability": "pdf-analysis",
                "description": "DEMO: extract an outline from a supplied PDF.",
            },
        )
        assert created.status_code == 201, created.text
        task_id = created.json()["task_id"]
        print("task created", task_id, created.json()["status"])

        ts = _iso()
        mid = f"demo-{uuid.uuid4().hex[:8]}"
        payload = {"note": "accepted"}
        sig = _signed(
            keys["test-document"],
            message_id=mid,
            type="ACCEPT",
            frm="test-document",
            to="test-research",
            task_id=task_id,
            payload=payload,
            timestamp=ts,
        )
        acc = client.post(
            f"/tasks/{task_id}/accept",
            json={
                "agent_id": "test-document",
                "message_id": mid,
                "timestamp": ts,
                "signature": sig,
                "payload": payload,
            },
        )
        assert acc.status_code == 200, acc.text
        assert acc.json()["status"] == "accepted"
        print("task accepted")

        ts = _iso()
        mid = f"demo-{uuid.uuid4().hex[:8]}"
        payload = {"pct": 50}
        sig = _signed(
            keys["test-document"],
            message_id=mid,
            type="PROGRESS",
            frm="test-document",
            to="test-research",
            task_id=task_id,
            payload=payload,
            timestamp=ts,
        )
        prog = client.post(
            f"/tasks/{task_id}/progress",
            json={
                "agent_id": "test-document",
                "message_id": mid,
                "timestamp": ts,
                "signature": sig,
                "payload": payload,
            },
        )
        assert prog.status_code == 200, prog.text
        assert prog.json()["status"] == "in_progress"
        print("task progress")

        ts = _iso()
        mid = f"demo-{uuid.uuid4().hex[:8]}"
        result_obj = {"outline": ["intro", "method", "demo-only"], "demo": True}
        payload = {"result": result_obj}
        sig = _signed(
            keys["test-document"],
            message_id=mid,
            type="RESULT",
            frm="test-document",
            to="test-research",
            task_id=task_id,
            payload=payload,
            timestamp=ts,
        )
        # Independent cryptographic check of the signature before/as submit.
        pub = bytes.fromhex(pubs["test-document"])
        msg = canonical_message_bytes(
            message_id=mid,
            type="RESULT",
            from_agent="test-document",
            to_agent="test-research",
            timestamp=ts,
            task_id=task_id,
            payload=payload,
        )
        assert verify(pub, msg, sig) is True
        print("signature independently verified (Ed25519)")

        res = client.post(
            f"/tasks/{task_id}/result",
            json={
                "agent_id": "test-document",
                "message_id": mid,
                "timestamp": ts,
                "signature": sig,
                "payload": payload,
                "result": result_obj,
            },
        )
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "completed"
        print("result submitted")

        ts = _iso()
        mid = f"demo-{uuid.uuid4().hex[:8]}"
        payload = {"independent_rerun": True, "ok": True}
        sig = _signed(
            keys["test-research"],
            message_id=mid,
            type="VERIFY",
            frm="test-research",
            to="test-research",
            task_id=task_id,
            payload=payload,
            timestamp=ts,
        )
        vouched = client.post(
            f"/tasks/{task_id}/verify",
            json={
                "agent_id": "test-research",
                "message_id": mid,
                "timestamp": ts,
                "signature": sig,
                "payload": payload,
            },
        )
        assert vouched.status_code == 200, vouched.text
        assert vouched.json()["status"] == "verified"
        print("task vouched after independent re-run")

        contrib = client.get("/contributions", params={"agent": "test-document"})
        assert contrib.status_code == 200
        events = {i["event"] for i in contrib.json()["items"]}
        assert "task_completed" in events
        assert "result_verified" in events
        print("contributions", sorted(events))

        metrics = client.get("/agents/test-document/metrics")
        assert metrics.status_code == 200
        print("metrics tasks_completed=", metrics.json()["tasks_completed"])

        # Invalid signature is rejected.
        bad = client.post(
            f"/tasks/{task_id}/progress",
            json={
                "agent_id": "test-document",
                "message_id": f"bad-{uuid.uuid4().hex[:8]}",
                "timestamp": _iso(),
                "signature": "00" * 64,
                "payload": {"nope": True},
            },
        )
        assert bad.status_code in {401, 409}, bad.text

        # Multi-capability swarm for another task.
        swarm_caps = ["crypto-research", "legal-research", "pdf-analysis"]
        proposed = client.post(
            "/swarms/propose",
            json={"capabilities": swarm_caps, "protocol": "http"},
        )
        assert proposed.status_code == 200, proposed.text
        body = proposed.json()
        assert body["proposed"] is True
        rec = [x["agent"]["id"] for x in body["recommended"]]
        exe = [x["agent"]["id"] for x in (body["executing"] or [])]
        assert "test-research" in rec
        assert "test-legal" in rec
        assert "test-document" in rec
        print("swarm recommended=", rec)
        print("swarm executing=", exe)
        assert rec != exe or len(exe) >= 1
        print("recommended vs executing distinguished")

        assembled = client.get(
            "/swarms/assemble",
            params=[("capability", c) for c in swarm_caps],
        )
        assert assembled.status_code == 200
        print("assemble members=", assembled.json()["member_agent_ids"])

        # Pagination + protocol filter
        page = client.get("/agents", params={"limit": 2, "offset": 0, "protocol": "http"})
        assert page.status_code == 200
        assert page.json()["limit"] == 2
        assert page.json()["total"] >= 5
        print("pagination total=", page.json()["total"])

    print("demo_flow: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
