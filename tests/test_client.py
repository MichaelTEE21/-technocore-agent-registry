from tests.conftest import AGENT_A, AGENT_B

from tar.crypto import canonical_message_bytes, generate_keypair, public_key_hex, sign
from tar_client import TarClient, TarClientError, connect


def test_python_client_discover_task_and_verify(client):
    priv, pub = generate_keypair()
    a = dict(AGENT_A)
    a["public_key"] = public_key_hex(pub)
    assert client.post("/agents", json=a).status_code == 201
    assert client.post("/agents", json=AGENT_B).status_code == 201

    tar = connect("http://testserver", client=client)
    found = tar.discover(["pdf-analysis"])
    assert found["count"] >= 1
    task = tar.create_task(
        requester="test-research",
        requested_capability="pdf-analysis",
        assignee="test-document",
        description="client demo",
        task_id="task-client-1",
    )
    assert task["task_id"] == "task-client-1"
    assert tar.get_task("task-client-1")["status"] == "requested"

    accepted = tar.accept("task-client-1", "test-document")
    assert accepted["status"] == "accepted"
    progressed = tar.progress("task-client-1", "test-document", payload={"pct": 50})
    assert progressed["status"] == "in_progress"
    done = tar.result("task-client-1", "test-document", result={"ok": True})
    assert done["status"] == "completed"

    listed = client.get("/messages", params={"task_id": "task-client-1", "type": "RESULT"})
    mid = listed.json()["items"][0]["message_id"]
    msg = tar.get_message(mid)
    checked = tar.verify_message(msg)
    assert checked["signature_status"] == "UNSIGNED"
    assert checked["valid"] is False

    envelope = dict(msg)
    envelope["payload"] = {"result": {"ok": False}}
    # unsigned still unsigned even if payload differs
    assert tar.verify_message(envelope)["signature_status"] == "UNSIGNED"

    # signed envelope with altered payload fails local verify
    ts = msg["timestamp"]
    payload = {"note": "ok"}
    mid2 = "msg-client-signed"
    sig = sign(
        priv,
        canonical_message_bytes(
            message_id=mid2,
            type="PROGRESS",
            from_agent="test-research",
            to_agent="test-document",
            timestamp=ts,
            task_id="task-client-1",
            payload=payload,
        ),
    )
    signed = {
        "message_id": mid2,
        "type": "PROGRESS",
        "from": "test-research",
        "to": "test-document",
        "timestamp": ts,
        "task_id": "task-client-1",
        "payload": payload,
        "signature": sig,
    }
    assert tar.verify_message(signed, public_key=public_key_hex(pub))["signature_status"] == "VALID"
    tampered = dict(signed)
    tampered["payload"] = {"note": "nope"}
    assert tar.verify_message(tampered, public_key=public_key_hex(pub))["signature_status"] == "INVALID"

    try:
        tar.create_task(
            requester="test-research",
            requested_capability="pdf-analysis",
            assignee="test-document",
            description="dup",
            task_id="task-client-1",
        )
        raise AssertionError("expected conflict")
    except TarClientError as exc:
        assert exc.status_code == 409


def test_client_connect_sets_base_url():
    tar = TarClient()
    tar.connect("http://127.0.0.1:8080")
    assert tar.base_url == "http://127.0.0.1:8080"
    tar.close()
