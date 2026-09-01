from tests.conftest import AGENT_A, AGENT_B, AGENT_C


def test_swarm_crud_and_assemble(client):
    for payload in (AGENT_A, AGENT_B, AGENT_C):
        assert client.post("/agents", json=payload).status_code == 201

    created = client.post(
        "/swarms",
        json={
            "id": "demo-core",
            "name": "Demo Core Swarm",
            "description": "FICTIONAL example swarm of three test agents.",
            "member_agent_ids": ["test-research", "test-document", "test-developer"],
            "required_capabilities": ["crypto-research", "pdf-analysis", "python"],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert set(body["member_agent_ids"]) == {
        "test-research",
        "test-document",
        "test-developer",
    }
    assert body["persisted"] is True

    listed = client.get("/swarms")
    assert listed.status_code == 200
    assert listed.json()["count"] == 1

    one = client.get("/swarms/demo-core")
    assert one.status_code == 200
    assert len(one.json()["members"]) == 3

    assembled = client.get("/swarms/assemble", params={"capability": "crypto-research"})
    assert assembled.status_code == 200
    proposed = assembled.json()
    assert proposed["proposed"] is True
    assert proposed["persisted"] is False
    assert "test-research" in proposed["member_agent_ids"]
    assert proposed["note"]

    # offline agents are excluded; unknown/online included (no invented liveness)
    client.put("/agents/test-research", json={"status": "offline"})
    assembled2 = client.get("/swarms/assemble", params={"capability": "crypto-research"})
    assert assembled2.json()["member_agent_ids"] == []
