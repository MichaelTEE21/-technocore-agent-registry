from tests.conftest import AGENT_A, AGENT_B, AGENT_C


def register_abc(client):
    for payload in (AGENT_A, AGENT_B, AGENT_C):
        resp = client.post("/agents", json=payload)
        assert resp.status_code == 201, resp.text
    return resp


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "technocore-agent-registry"


def test_register_query_search_profile_verification(client):
    register_abc(client)

    caps = client.get("/capabilities")
    assert caps.status_code == 200
    data = caps.json()
    ids = {item["id"] for item in data["items"]}
    assert "crypto-research" in ids
    assert "pdf-analysis" in ids
    assert "python" in ids
    assert "agent-orchestration" in ids
    assert "task-delegation" in ids

    one = client.get("/capabilities/crypto-research")
    assert one.status_code == 200
    assert one.json()["id"] == "crypto-research"

    found = client.get("/agents", params={"capability": "crypto-research"})
    assert found.status_code == 200
    body = found.json()
    assert body["count"] == 1
    assert body["items"][0]["id"] == "test-research"

    profile = client.get("/agents/test-research")
    assert profile.status_code == 200
    agent = profile.json()
    assert agent["did"] == "did:example:test-research"
    assert {c["id"] for c in agent["capabilities"]} == {
        "crypto-research",
        "web-research",
        "source-verification",
    }
    assert agent["verification"]["status"] == "claimed"
    assert agent["fictional"] is True

    ver = client.get("/agents/test-research/verification")
    assert ver.status_code == 200
    vbody = ver.json()
    assert vbody["current_status"] == "claimed"
    assert vbody["items"]


def test_filters_and_update_delete(client):
    register_abc(client)
    by_cat = client.get("/agents", params={"category": "software"})
    assert by_cat.json()["count"] == 1
    by_status = client.get("/agents", params={"status": "unknown"})
    assert by_status.json()["count"] == 1
    upd = client.put("/agents/test-developer", json={"status": "busy"})
    assert upd.status_code == 200
    assert upd.json()["status"] == "busy"
    gone = client.delete("/agents/test-developer")
    assert gone.status_code == 204
    assert client.get("/agents/test-developer").status_code == 404


def test_conflict_and_not_found(client):
    client.post("/agents", json=AGENT_A)
    again = client.post("/agents", json=AGENT_A)
    assert again.status_code == 409
    missing = client.get("/agents/nope")
    assert missing.status_code == 404
    assert "error" in missing.json()


def test_extra_fields_ignored(client):
    payload = dict(AGENT_A)
    payload["id"] = "test-extra"
    payload["did"] = "did:example:test-extra"
    payload["unknownFuture"] = {"foo": 1}
    resp = client.post("/agents", json=payload)
    assert resp.status_code == 201
    assert "unknownFuture" not in resp.json()


def test_rejects_private_key_fields(client):
    payload = dict(AGENT_A)
    payload["id"] = "evil"
    payload["did"] = "did:example:evil"
    payload["privateKey"] = "would-be-secret"
    resp = client.post("/agents", json=payload)
    assert resp.status_code == 422
