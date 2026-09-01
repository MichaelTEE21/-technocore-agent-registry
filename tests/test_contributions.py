from tests.conftest import AGENT_A, AGENT_B


def test_contributions_and_metrics(client):
    client.post("/agents", json=AGENT_A)
    client.post("/agents", json=AGENT_B)
    created = client.post(
        "/tasks",
        json={
            "requester": "test-research",
            "assignee": "test-document",
            "requested_capability": "pdf-analysis",
            "description": "demo",
        },
    )
    task_id = created.json()["task_id"]
    client.post(f"/tasks/{task_id}/accept", json={"agent_id": "test-document"})
    client.post(f"/tasks/{task_id}/progress", json={"agent_id": "test-document"})
    client.post(f"/tasks/{task_id}/result", json={"agent_id": "test-document", "result": {"ok": True}})
    client.post(f"/tasks/{task_id}/verify", json={"agent_id": "test-research"})
    rows = client.get("/contributions", params={"agent": "test-document"})
    assert rows.status_code == 200
    events = {i["event"] for i in rows.json()["items"]}
    assert "task_completed" in events
    assert "result_verified" in events
    metrics = client.get("/agents/test-document/metrics")
    body = metrics.json()
    assert body["tasks_completed"] >= 1
    assert body["results_verified"] >= 1
    assert "score" not in body
    endorse = client.post(
        "/contributions",
        json={
            "agent_id": "test-document",
            "event": "community_endorsement",
            "detail": "demo endorsement",
        },
    )
    assert endorse.status_code == 201
