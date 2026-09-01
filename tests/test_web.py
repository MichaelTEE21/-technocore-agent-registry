from tests.conftest import AGENT_A, AGENT_B, AGENT_C


def test_html_pages(client):
    for payload in (AGENT_A, AGENT_B, AGENT_C):
        client.post("/agents", json=payload)
    client.post(
        "/swarms",
        json={
            "id": "demo-core",
            "name": "Demo Core Swarm",
            "description": "FICTIONAL example swarm of three test agents.",
            "member_agent_ids": ["test-research", "test-document", "test-developer"],
            "required_capabilities": ["crypto-research"],
        },
    )
    home = client.get("/")
    assert home.status_code == 200
    assert b"Research Agent" in home.content
    profile = client.get("/ui/agents/test-research")
    assert profile.status_code == 200
    assert b"did:example:test-research" in profile.content
    swarms = client.get("/ui/swarms")
    assert swarms.status_code == 200
    assert b"Demo Core Swarm" in swarms.content
    caps = client.get("/ui/capabilities")
    assert caps.status_code == 200
    assert b"crypto-research" in caps.content
    tasks = client.get("/ui/tasks")
    assert tasks.status_code == 200
    contrib = client.get("/ui/contributions")
    assert contrib.status_code == 200
    disc = client.get("/ui/discover", params={"q": "python"})
    assert disc.status_code == 200
