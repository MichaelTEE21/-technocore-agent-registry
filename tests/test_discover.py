from tests.conftest import AGENT_A, AGENT_B, AGENT_C


def test_discover_ranking_and_pagination(client):
    for payload in (AGENT_A, AGENT_B, AGENT_C):
        assert client.post("/agents", json=payload).status_code == 201
    disc = client.get("/discover", params=[("capability", "crypto-research"), ("capability", "web-research")])
    assert disc.status_code == 200
    body = disc.json()
    assert body["count"] >= 1
    assert body["items"][0]["rank_breakdown"]
    assert "weights" in body["ranking"]
    page = client.get("/agents", params={"limit": 1, "offset": 0, "protocol": "http"})
    assert page.status_code == 200
    assert page.json()["count"] == 1
    assert page.json()["total"] == 3
    page2 = client.get("/agents", params={"limit": 1, "offset": 1})
    assert page2.json()["items"][0]["id"] != page.json()["items"][0]["id"]


def test_swarm_multi_capability_roles(client):
    for payload in (AGENT_A, AGENT_B, AGENT_C):
        client.post("/agents", json=payload)
    proposed = client.post(
        "/swarms/propose",
        json={"capabilities": ["crypto-research", "pdf-analysis", "python"]},
    )
    assert proposed.status_code == 200, proposed.text
    body = proposed.json()
    assert body["recommended"]
    assert body["executing"]
    rec_ids = {x["agent"]["id"] for x in body["recommended"]}
    exe_ids = {x["agent"]["id"] for x in body["executing"]}
    assert rec_ids >= exe_ids
    assert "test-research" in rec_ids
