from tests.conftest import AGENT_A, AGENT_B, AGENT_C


def _register(client):
    for payload in (AGENT_A, AGENT_B, AGENT_C):
        assert client.post("/agents", json=payload).status_code == 201


def test_task_happy_path_and_invalid_transition(client):
    _register(client)
    created = client.post(
        "/tasks",
        json={
            "requester": "test-research",
            "assignee": "test-document",
            "requested_capability": "pdf-analysis",
            "description": "DEMO outline",
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["task_id"]
    assert created.json()["status"] == "requested"

    too_soon = client.post(
        f"/tasks/{task_id}/result",
        json={"agent_id": "test-document", "payload": {"result": {"x": 1}}},
    )
    assert too_soon.status_code == 409

    acc = client.post(f"/tasks/{task_id}/accept", json={"agent_id": "test-document"})
    assert acc.status_code == 200
    assert acc.json()["status"] == "accepted"

    prog = client.post(
        f"/tasks/{task_id}/progress",
        json={"agent_id": "test-document", "payload": {"pct": 10}},
    )
    assert prog.status_code == 200
    assert prog.json()["status"] == "in_progress"

    done = client.post(
        f"/tasks/{task_id}/result",
        json={"agent_id": "test-document", "result": {"ok": True}},
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "completed"

    self_vouch = client.post(f"/tasks/{task_id}/verify", json={"agent_id": "test-document"})
    assert self_vouch.status_code == 403

    vouched = client.post(f"/tasks/{task_id}/verify", json={"agent_id": "test-research"})
    assert vouched.status_code == 200
    assert vouched.json()["status"] == "verified"

    listed = client.get("/tasks")
    assert listed.status_code == 200
    assert listed.json()["count"] >= 1


def test_reject_and_unknown_assignee_capability(client):
    _register(client)
    bad = client.post(
        "/tasks",
        json={
            "requester": "test-research",
            "assignee": "test-developer",
            "requested_capability": "pdf-analysis",
            "description": "wrong worker",
        },
    )
    assert bad.status_code == 400

    created = client.post(
        "/tasks",
        json={
            "requester": "test-research",
            "assignee": "test-document",
            "requested_capability": "pdf-analysis",
            "description": "nope",
        },
    )
    task_id = created.json()["task_id"]
    rej = client.post(f"/tasks/{task_id}/reject", json={"agent_id": "test-document"})
    assert rej.status_code == 200
    assert rej.json()["status"] == "rejected"
    again = client.post(f"/tasks/{task_id}/accept", json={"agent_id": "test-document"})
    assert again.status_code == 409
