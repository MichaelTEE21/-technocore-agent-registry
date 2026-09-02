"""A2A Communication MVP: directed tasks, history, SUBMIT alias, transitions."""

from __future__ import annotations

from tests.test_productionize import KNOWN_DID, KNOWN_PUB_HEX

DEMO_DESCRIPTION = "Analyse the tokenomics of Project X."
DEMO_RESULT = {
    "summary": "Placeholder tokenomics analysis for Project X (demo).",
    "token_supply": "1_000_000_000",
    "allocation": "Team 20% · Community 40% · Treasury 40%",
    "vesting": "24-month linear with 6-month cliff",
}

AGENT_A = {
    "id": "mananze-technocore-agent",
    "name": "Mananze Technocore Agent",
    "did": KNOWN_DID,
    "description": "Independent open-source registration. Not official Technocore membership.",
    "capabilities": [
        {"id": "crypto-research", "category": "crypto-web3", "level": "advanced"},
        {"id": "web-research", "category": "research", "level": "advanced"},
    ],
    "protocols": ["http", "a2a"],
    "status": "online",
    "endpoint": "https://example.invalid/agents/mananze",
}

AGENT_B = {
    "id": "a2a-tokenomics-worker",
    "name": "Tokenomics Worker B",
    "did": "did:example:a2a-tokenomics-worker",
    "description": "FICTIONAL demo worker advertising tokenomics-analysis.",
    "capabilities": [
        {"id": "tokenomics-analysis", "category": "crypto-web3", "level": "advanced"},
        {"id": "defi-analysis", "category": "crypto-web3", "level": "intermediate"},
    ],
    "protocols": ["http", "a2a"],
    "status": "online",
    "fictional": True,
}


def _register(client, *agents):
    for payload in agents:
        resp = client.post("/agents", json=payload)
        assert resp.status_code == 201, resp.text


def test_a2a_happy_path_discover_accept_submit(client):
    _register(client, AGENT_A, AGENT_B)

    discovered = client.get("/discover", params={"capability": "tokenomics-analysis"})
    assert discovered.status_code == 200
    ids = [i["agent"]["id"] for i in discovered.json()["items"]]
    assert "a2a-tokenomics-worker" in ids

    created = client.post(
        "/tasks",
        json={
            "requester": "mananze-technocore-agent",
            "assignee": "a2a-tokenomics-worker",
            "requested_capability": "tokenomics-analysis",
            "description": DEMO_DESCRIPTION,
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    task_id = body["task_id"]
    assert body["status"] == "requested"
    assert body["assignee"] == "a2a-tokenomics-worker"
    assert body["target_agent_id"] == "a2a-tokenomics-worker"
    assert body["accepted_at"] is None
    assert body["completed_at"] is None

    msgs = client.get("/messages", params={"task_id": task_id})
    assert msgs.status_code == 200
    types = [m["type"] for m in msgs.json()["items"]]
    assert "REQUEST" in types

    acc = client.post(
        f"/tasks/{task_id}/accept",
        json={"agent_id": "a2a-tokenomics-worker"},
    )
    assert acc.status_code == 200, acc.text
    assert acc.json()["status"] == "accepted"
    assert acc.json()["accepted_at"] is not None

    submitted = client.post(
        f"/tasks/{task_id}/submit",
        json={"agent_id": "a2a-tokenomics-worker", "result": DEMO_RESULT},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "completed"
    assert submitted.json()["completed_at"] is not None
    assert submitted.json()["result"]["token_supply"] == DEMO_RESULT["token_supply"]

    as_a = client.get(f"/tasks/{task_id}")
    assert as_a.status_code == 200
    assert as_a.json()["result"]["allocation"] == DEMO_RESULT["allocation"]
    assert as_a.json()["result"]["vesting"] == DEMO_RESULT["vesting"]

    history = client.get(f"/tasks/{task_id}/history")
    assert history.status_code == 200
    h = history.json()
    assert h["task_id"] == task_id
    event_names = [e["event"] for e in h["events"]]
    assert "created" in event_names
    assert "accepted" in event_names
    assert "result" in event_names
    msg_types = [m["type"] for m in h["messages"]]
    assert "REQUEST" in msg_types
    assert "ACCEPT" in msg_types
    assert "RESULT" in msg_types

    events_alias = client.get(f"/tasks/{task_id}/events")
    assert events_alias.status_code == 200
    assert len(events_alias.json()["events"]) == len(h["events"])


def test_a2a_target_agent_id_alias_on_create(client):
    _register(client, AGENT_A, AGENT_B)
    created = client.post(
        "/tasks",
        json={
            "requester": "mananze-technocore-agent",
            "target_agent_id": "a2a-tokenomics-worker",
            "requested_capability": "tokenomics-analysis",
            "description": DEMO_DESCRIPTION,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["assignee"] == "a2a-tokenomics-worker"
    assert created.json()["target_agent_id"] == "a2a-tokenomics-worker"


def test_a2a_reject_path(client):
    _register(client, AGENT_A, AGENT_B)
    created = client.post(
        "/tasks",
        json={
            "requester": "mananze-technocore-agent",
            "assignee": "a2a-tokenomics-worker",
            "requested_capability": "tokenomics-analysis",
            "description": DEMO_DESCRIPTION,
        },
    )
    task_id = created.json()["task_id"]
    rej = client.post(
        f"/tasks/{task_id}/reject",
        json={"agent_id": "a2a-tokenomics-worker"},
    )
    assert rej.status_code == 200
    assert rej.json()["status"] == "rejected"
    # cannot accept after reject
    again = client.post(
        f"/tasks/{task_id}/accept",
        json={"agent_id": "a2a-tokenomics-worker"},
    )
    assert again.status_code == 409


def test_a2a_invalid_transitions(client):
    _register(client, AGENT_A, AGENT_B)
    created = client.post(
        "/tasks",
        json={
            "requester": "mananze-technocore-agent",
            "assignee": "a2a-tokenomics-worker",
            "requested_capability": "tokenomics-analysis",
            "description": DEMO_DESCRIPTION,
        },
    )
    task_id = created.json()["task_id"]

    # submit while still requested → 409
    too_soon = client.post(
        f"/tasks/{task_id}/result",
        json={"agent_id": "a2a-tokenomics-worker", "result": DEMO_RESULT},
    )
    assert too_soon.status_code == 409

    client.post(f"/tasks/{task_id}/accept", json={"agent_id": "a2a-tokenomics-worker"})
    client.post(
        f"/tasks/{task_id}/submit",
        json={"agent_id": "a2a-tokenomics-worker", "result": DEMO_RESULT},
    )
    # accept completed → 409
    accept_done = client.post(
        f"/tasks/{task_id}/accept",
        json={"agent_id": "a2a-tokenomics-worker"},
    )
    assert accept_done.status_code == 409

    # reject path then submit
    created2 = client.post(
        "/tasks",
        json={
            "requester": "mananze-technocore-agent",
            "assignee": "a2a-tokenomics-worker",
            "requested_capability": "tokenomics-analysis",
            "description": "reject then submit",
        },
    )
    tid2 = created2.json()["task_id"]
    client.post(f"/tasks/{tid2}/reject", json={"agent_id": "a2a-tokenomics-worker"})
    submit_rej = client.post(
        f"/tasks/{tid2}/submit",
        json={"agent_id": "a2a-tokenomics-worker", "result": DEMO_RESULT},
    )
    assert submit_rej.status_code == 409


def test_a2a_nonexistent_agent_and_wrong_parties(client):
    _register(client, AGENT_A, AGENT_B)
    missing = client.post(
        "/tasks",
        json={
            "requester": "mananze-technocore-agent",
            "assignee": "does-not-exist",
            "requested_capability": "tokenomics-analysis",
            "description": DEMO_DESCRIPTION,
        },
    )
    assert missing.status_code == 404

    # capability mismatch
    bad_cap = client.post(
        "/tasks",
        json={
            "requester": "mananze-technocore-agent",
            "assignee": "a2a-tokenomics-worker",
            "requested_capability": "python",
            "description": DEMO_DESCRIPTION,
        },
    )
    assert bad_cap.status_code == 400

    created = client.post(
        "/tasks",
        json={
            "requester": "mananze-technocore-agent",
            "assignee": "a2a-tokenomics-worker",
            "requested_capability": "tokenomics-analysis",
            "description": DEMO_DESCRIPTION,
        },
    )
    task_id = created.json()["task_id"]

    # wrong agent accepts (requester trying to accept as if assignee when assignee set)
    wrong = client.post(
        f"/tasks/{task_id}/accept",
        json={"agent_id": "mananze-technocore-agent"},
    )
    assert wrong.status_code == 403

    client.post(f"/tasks/{task_id}/accept", json={"agent_id": "a2a-tokenomics-worker"})
    # wrong party submits
    wrong_submit = client.post(
        f"/tasks/{task_id}/submit",
        json={"agent_id": "mananze-technocore-agent", "result": DEMO_RESULT},
    )
    assert wrong_submit.status_code == 403


def test_a2a_history_persistence_and_result_endpoint_parity(client):
    _register(client, AGENT_A, AGENT_B)
    created = client.post(
        "/tasks",
        json={
            "requester": "mananze-technocore-agent",
            "assignee": "a2a-tokenomics-worker",
            "requested_capability": "tokenomics-analysis",
            "description": DEMO_DESCRIPTION,
        },
    )
    task_id = created.json()["task_id"]
    client.post(f"/tasks/{task_id}/accept", json={"agent_id": "a2a-tokenomics-worker"})
    # /result still works (SUBMIT is alias)
    done = client.post(
        f"/tasks/{task_id}/result",
        json={"agent_id": "a2a-tokenomics-worker", "result": DEMO_RESULT},
    )
    assert done.status_code == 200
    hist = client.get(f"/tasks/{task_id}/history").json()
    assert len(hist["events"]) >= 3
    assert len(hist["messages"]) >= 3
    # pubkey on A preserved from productionize path
    agent_a = client.get("/agents/mananze-technocore-agent").json()
    assert agent_a["public_key"] == KNOWN_PUB_HEX
    assert agent_a["did"] == KNOWN_DID


def test_a2a_protocol_aliases_and_flop_stub():
    from tar.a2a import FLOP_ADAPTATION, MESSAGE_TYPE_ALIASES, ProtocolAdapter

    assert MESSAGE_TYPE_ALIASES["task.submit"] == "RESULT"
    assert MESSAGE_TYPE_ALIASES["SUBMIT"] == "RESULT"
    assert FLOP_ADAPTATION["claim"] == "not_official_flop"
    adapter = ProtocolAdapter()
    assert adapter.to_external("RESULT") == "flop.task.result"
    assert adapter.to_external("task.submit") == "flop.task.result"
    assert adapter.from_external("flop.task.request") == "REQUEST"


def test_a2a_communicate_ui(client):
    _register(client, AGENT_A, AGENT_B)
    page = client.get(
        "/ui/communicate",
        params={
            "requester": "mananze-technocore-agent",
            "assignee": "a2a-tokenomics-worker",
            "capability": "tokenomics-analysis",
        },
    )
    assert page.status_code == 200
    assert b"Agent-to-agent task" in page.content
    assert b"tokenomics-analysis" in page.content
    assert b"Send TASK" in page.content

    nav = client.get("/")
    assert nav.status_code == 200
    assert b"/ui/communicate" in nav.content

    created = client.post(
        "/ui/communicate",
        data={
            "action": "create",
            "requester": "mananze-technocore-agent",
            "assignee": "a2a-tokenomics-worker",
            "capability": "tokenomics-analysis",
            "description": DEMO_DESCRIPTION,
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    loc = created.headers["location"]
    assert "task_id=" in loc

    # follow to get task_id
    followed = client.get(loc)
    assert followed.status_code == 200
    assert DEMO_DESCRIPTION.encode() in followed.content or b"requested" in followed.content
