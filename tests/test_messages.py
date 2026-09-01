from datetime import UTC, datetime

from tests.conftest import AGENT_A, AGENT_B


def test_message_validation_and_replay(client):
    assert client.post("/agents", json=AGENT_A).status_code == 201
    assert client.post("/agents", json=AGENT_B).status_code == 201
    ts = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    body = {
        "message_id": "msg-unique-1",
        "type": "REQUEST",
        "from": "test-research",
        "to": "test-document",
        "timestamp": ts,
        "payload": {"requested_capability": "pdf-analysis", "description": "demo"},
    }
    first = client.post("/messages", json=body)
    assert first.status_code == 201, first.text
    replay = client.post("/messages", json=body)
    assert replay.status_code == 409
    listed = client.get("/messages")
    assert listed.status_code == 200
    assert listed.json()["count"] >= 1

    bad_type = dict(body)
    bad_type["message_id"] = "msg-unique-2"
    bad_type["type"] = "NOPE"
    assert client.post("/messages", json=bad_type).status_code == 422
