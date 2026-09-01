import uuid
from datetime import UTC, datetime

from tests.conftest import AGENT_A, AGENT_B

from tar.crypto import canonical_message_bytes, generate_keypair, public_key_hex, sign, verify


def _iso():
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def test_valid_and_invalid_signatures(client):
    priv, pub = generate_keypair()
    a = dict(AGENT_A)
    a["public_key"] = public_key_hex(pub)
    b = dict(AGENT_B)
    assert client.post("/agents", json=a).status_code == 201
    assert client.post("/agents", json=b).status_code == 201

    created = client.post(
        "/tasks",
        json={
            "requester": "test-document",
            "assignee": "test-research",
            "requested_capability": "crypto-research",
            "description": "signed demo",
        },
    )
    task_id = created.json()["task_id"]
    ts = _iso()
    mid = f"sig-{uuid.uuid4().hex[:8]}"
    payload = {"note": "ok"}
    sig = sign(
        priv,
        canonical_message_bytes(
            message_id=mid,
            type="ACCEPT",
            from_agent="test-research",
            to_agent="test-document",
            timestamp=ts,
            task_id=task_id,
            payload=payload,
        ),
    )
    assert verify(pub, canonical_message_bytes(
        message_id=mid, type="ACCEPT", from_agent="test-research", to_agent="test-document",
        timestamp=ts, task_id=task_id, payload=payload,
    ), sig)

    ok = client.post(
        f"/tasks/{task_id}/accept",
        json={
            "agent_id": "test-research",
            "message_id": mid,
            "timestamp": ts,
            "signature": sig,
            "payload": payload,
        },
    )
    assert ok.status_code == 200, ok.text

    bad = client.post(
        f"/tasks/{task_id}/progress",
        json={
            "agent_id": "test-research",
            "message_id": f"sig-{uuid.uuid4().hex[:8]}",
            "timestamp": _iso(),
            "signature": "ab" * 64,
            "payload": {"pct": 1},
        },
    )
    assert bad.status_code == 401


def test_rejects_private_key_on_profile(client):
    payload = dict(AGENT_A)
    payload["id"] = "test-keys"
    payload["did"] = "did:example:test-keys"
    payload["private_key"] = "aa" * 32
    resp = client.post("/agents", json=payload)
    assert resp.status_code == 422
