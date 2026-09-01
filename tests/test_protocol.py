"""Protocol contract, replay/idempotency, message verify, START scripts."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from tests.conftest import AGENT_A, AGENT_B, AGENT_C, ROOT

from tar.a2a import PROTOCOL_NAME, PROTOCOL_VERSION
from tar.crypto import canonical_message_bytes, generate_keypair, public_key_hex, sign, verify


def test_protocol_name_and_version():
    assert PROTOCOL_NAME == "tar.a2a"
    assert PROTOCOL_VERSION == "1.0"


def test_json_schemas_exist_and_are_json_only():
    folder = ROOT / "docs" / "protocol"
    for name in ("message.schema.json", "task.schema.json", "error.schema.json", "protocol.json"):
        data = json.loads((folder / name).read_text(encoding="utf-8"))
        assert isinstance(data, dict)
    proto = json.loads((folder / "protocol.json").read_text(encoding="utf-8"))
    assert proto["protocol"] == "tar.a2a"
    assert proto["protocol_version"] == "1.0"
    msg = json.loads((folder / "message.schema.json").read_text(encoding="utf-8"))
    assert "message_id" in msg["required"]
    task = json.loads((folder / "task.schema.json").read_text(encoding="utf-8"))
    states = set(task["properties"]["status"]["enum"])
    assert states == {
        "requested",
        "accepted",
        "rejected",
        "in_progress",
        "completed",
        "failed",
        "verified",
        "disputed",
    }
    err = json.loads((folder / "error.schema.json").read_text(encoding="utf-8"))
    assert err["properties"]["error"]["required"] == ["code", "message"]
    contract = (ROOT / "docs" / "protocol.md").read_text(encoding="utf-8")
    assert "SQLAlchemy" in contract
    assert "not distributed consensus" in contract.lower() or "not distributed consensus" in contract
    assert "Identity check" in contract


def test_duplicate_message_id_is_409(client):
    assert client.post("/agents", json=AGENT_A).status_code == 201
    assert client.post("/agents", json=AGENT_B).status_code == 201
    ts = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    body = {
        "message_id": "msg-dup-freeze",
        "type": "REQUEST",
        "from": "test-research",
        "to": "test-document",
        "timestamp": ts,
        "payload": {"requested_capability": "pdf-analysis", "description": "dup"},
    }
    first = client.post("/messages", json=body)
    assert first.status_code == 201, first.text
    replay = client.post("/messages", json=body)
    assert replay.status_code == 409
    assert replay.json()["error"]["code"] == "conflict"
    listed = client.get("/messages", params={"from": "test-research"})
    ids = [m["message_id"] for m in listed.json()["items"]]
    assert ids.count("msg-dup-freeze") == 1


def test_duplicate_task_id_is_409(client):
    for payload in (AGENT_A, AGENT_B):
        assert client.post("/agents", json=payload).status_code == 201
    body = {
        "requester": "test-research",
        "assignee": "test-document",
        "requested_capability": "pdf-analysis",
        "description": "dup task",
        "task_id": "task-dup-freeze",
    }
    first = client.post("/tasks", json=body)
    assert first.status_code == 201, first.text
    again = client.post("/tasks", json=body)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "conflict"


def test_invalid_transition_still_rejected(client):
    for payload in (AGENT_A, AGENT_B):
        assert client.post("/agents", json=payload).status_code == 201
    created = client.post(
        "/tasks",
        json={
            "requester": "test-research",
            "assignee": "test-document",
            "requested_capability": "pdf-analysis",
            "description": "too soon",
        },
    )
    task_id = created.json()["task_id"]
    too_soon = client.post(
        f"/tasks/{task_id}/result",
        json={"agent_id": "test-document", "payload": {"result": {"x": 1}}},
    )
    assert too_soon.status_code == 409
    acc = client.post(f"/tasks/{task_id}/accept", json={"agent_id": "test-document"})
    assert acc.status_code == 200
    again = client.post(f"/tasks/{task_id}/accept", json={"agent_id": "test-document"})
    assert again.status_code == 409


def test_altered_payload_fails_verify_and_message_verify_endpoint(client):
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
            "description": "signed freeze",
        },
    )
    task_id = created.json()["task_id"]
    ts = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    mid = "msg-sig-freeze"
    payload = {"note": "ok"}
    original = canonical_message_bytes(
        message_id=mid,
        type="ACCEPT",
        from_agent="test-research",
        to_agent="test-document",
        timestamp=ts,
        task_id=task_id,
        payload=payload,
    )
    sig = sign(priv, original)
    assert verify(pub, original, sig)
    altered = canonical_message_bytes(
        message_id=mid,
        type="ACCEPT",
        from_agent="test-research",
        to_agent="test-document",
        timestamp=ts,
        task_id=task_id,
        payload={"note": "tampered"},
    )
    assert not verify(pub, altered, sig)

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
    checked = client.post(f"/messages/{mid}/verify")
    assert checked.status_code == 200, checked.text
    body = checked.json()
    assert body["signature_status"] == "VALID"
    assert body["valid"] is True

    unsigned_msgs = client.get("/messages", params={"task_id": task_id, "type": "REQUEST"})
    req_id = unsigned_msgs.json()["items"][0]["message_id"]
    unsigned = client.post(f"/messages/{req_id}/verify")
    assert unsigned.json()["signature_status"] == "UNSIGNED"
    assert unsigned.json()["valid"] is False


def test_future_and_malformed_timestamp_rejected(client):
    assert client.post("/agents", json=AGENT_A).status_code == 201
    assert client.post("/agents", json=AGENT_B).status_code == 201
    future = (datetime.now(UTC) + timedelta(hours=2)).replace(microsecond=0)
    body = {
        "message_id": "msg-future-freeze",
        "type": "REQUEST",
        "from": "test-research",
        "to": "test-document",
        "timestamp": future.isoformat().replace("+00:00", "Z"),
        "payload": {"requested_capability": "pdf-analysis"},
    }
    resp = client.post("/messages", json=body)
    assert resp.status_code == 400
    bad = dict(body)
    bad["message_id"] = "msg-bad-ts"
    bad["timestamp"] = "not-a-date"
    assert client.post("/messages", json=bad).status_code == 400


def test_task_timeline_shows_events_and_signature_status(client):
    for payload in (AGENT_A, AGENT_B, AGENT_C):
        client.post("/agents", json=payload)
    created = client.post(
        "/tasks",
        json={
            "requester": "test-research",
            "assignee": "test-document",
            "requested_capability": "pdf-analysis",
            "description": "timeline",
        },
    )
    task_id = created.json()["task_id"]
    client.post(f"/tasks/{task_id}/accept", json={"agent_id": "test-document"})
    page = client.get(f"/ui/tasks/{task_id}")
    assert page.status_code == 200
    assert b"REQUEST" in page.content
    assert b"ACCEPT" in page.content
    assert b"UNSIGNED" in page.content
    assert b"test-research" in page.content
    assert b"test-document" in page.content


def test_start_scripts_banner_and_mananze():
    bat = (ROOT / "START.bat").read_text(encoding="utf-8")
    ps1 = (ROOT / "START.ps1").read_text(encoding="utf-8")
    for text in (bat, ps1):
        assert "MANANZE — TECHNOCORE AGENT REGISTRY" in text
        assert "Python environment not found. Please tell MANANZE." in text
        assert "127.0.0.1:8080" in text
        assert "uvicorn tar.main:app" in text
        assert "did:example:test-document" in text
        assert "ChatGPT" not in text
        assert "Enelo" not in text
