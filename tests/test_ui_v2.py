from tests.conftest import AGENT_A, AGENT_B, AGENT_C

FORBIDDEN_DID = b"did:key:z6Mkrv5ZL3VsapUdVKirgFiJVdw7y5w8Bq3zDvmfNMDSAAep"

PAGES = (
    "/",
    "/ui/lookup",
    "/ui/agents",
    "/ui/projects",
    "/ui/deployments",
    "/ui/settings",
    "/ui/agents/new",
    "/ui/discover",
    "/ui/capabilities",
    "/ui/tasks",
    "/ui/contributions",
    "/ui/protocol",
    "/ui/developers",
    "/ui/swarms",
)


def _seed(client):
    for payload in (AGENT_A, AGENT_B, AGENT_C):
        assert client.post("/agents", json=payload).status_code == 201


def test_landing_hero_and_did_form(client):
    _seed(client)
    home = client.get("/")
    assert home.status_code == 200
    body = home.content
    assert b"AGENT NETWORK" in body
    assert b"Discover agents. Connect capabilities. Get work done." in body
    assert b"Connect Agent" in body
    assert b"Explore Agents" in body
    assert b"View Protocol" in body
    assert b"Paste a public DID" in body
    assert b"Research Agent" in body
    assert FORBIDDEN_DID not in body
    assert b"Give it a face" not in body
    assert b"Agent City" not in body
    assert b"Registered" in body
    

def test_public_pages_ok_and_nav_targets(client):
    _seed(client)
    for path in PAGES:
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert FORBIDDEN_DID not in resp.content
        assert b"<nav" in resp.content
        # sidebar shell present
        assert b"sidebar" in resp.content or b"Overview" in resp.content


def test_directory_and_profile_avatar(client):
    _seed(client)
    listing = client.get("/ui/agents")
    assert listing.status_code == 200
    assert b"Document Agent" in listing.content
    assert b"View Agent" in listing.content
    assert b"Copy DID" in listing.content
    assert b"DEMO / FICTIONAL" in listing.content
    profile = client.get("/ui/agents/test-research")
    assert profile.status_code == 200
    assert b"did:example:test-research" in profile.content
    assert b"CLAIMED" in profile.content
    assert b"Proves" in profile.content
    assert b"Does not prove" in profile.content
    assert b"Overview" in profile.content
    assert b"Capabilities" in profile.content


def test_capability_explorer_lists_advertisers(client):
    _seed(client)
    page = client.get("/ui/capabilities/python")
    assert page.status_code == 200
    assert b"Developer Agent" in page.content
    assert b"not auto-verified" in page.content
    missing = client.get("/ui/capabilities/not-a-real-capability")
    assert missing.status_code == 404


def test_lookup_unknown_valid_and_empty_connect(client):
    empty = client.get("/ui/lookup")
    assert empty.status_code == 200
    assert b"Paste a public DID" in empty.content
    unknown = client.get("/ui/lookup", params={"did": "did:example:not-registered-xyz"})
    assert unknown.status_code == 200
    assert b"VALID PUBLIC DID" in unknown.content
    assert b"not in this local registry" in unknown.content
    pem = client.get(
        "/ui/lookup",
        params={"did": "-----BEGIN PRIVATE KEY-----\nX\n-----END PRIVATE KEY-----"},
    )
    assert pem.status_code == 400
    assert b"BEGIN PRIVATE" not in pem.content


def test_protocol_and_developers(client):
    proto = client.get("/ui/protocol")
    assert proto.status_code == 200
    assert b"tar.a2a" in proto.content
    assert b"message.schema.json" in proto.content
    schema = client.get("/ui/protocol/schemas/message.schema.json")
    assert schema.status_code == 200
    assert b"REQUEST" in schema.content
    dev = client.get("/ui/developers")
    assert dev.status_code == 200
    assert b"TarClient" in dev.content
    assert b"client.discover" in dev.content
    assert b"client.create_task" in dev.content
    assert b"client.accept" in dev.content
    assert b"client.result" in dev.content
    assert b"verify_message" in dev.content
    assert b"/docs" in dev.content


def test_discover_filters_and_task_caption(client):
    _seed(client)
    disc = client.get("/ui/discover", params={"q": "python"})
    assert disc.status_code == 200
    assert b"Developer Agent" in disc.content
    named = client.get("/ui/discover", params={"name": "Document"})
    assert named.status_code == 200
    assert b"Document Agent" in named.content
    created = client.post(
        "/tasks",
        json={
            "requester": "test-research",
            "assignee": "test-document",
            "requested_capability": "pdf-analysis",
            "description": "DEMO lookup",
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["task_id"]
    page = client.get(f"/ui/tasks/{task_id}")
    assert page.status_code == 200
    assert b"valid signature proves control of identity" in page.content
    assert b"Copy task ID" in page.content
    assert b"REQUEST" in page.content


def test_new_agent_flow_registers_and_redirects(client):
    page = client.get("/ui/agents/new")
    assert page.status_code == 200
    assert b"Register an agent" in page.content
    assert b"Public DID" in page.content
    resp = client.post(
        "/ui/agents/new",
        data={
            "name": "Wizard Agent",
            "id": "ui-wizard-1",
            "did": "did:example:ui-wizard-1",
            "description": "FICTIONAL UI registration test",
            "status": "online",
            "fictional": "true",
            "capability": ["python", "testing"],
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303, resp.text
    assert resp.headers["location"] == "/ui/agents/ui-wizard-1"
    profile = client.get("/ui/agents/ui-wizard-1")
    assert profile.status_code == 200
    assert b"Wizard Agent" in profile.content
    assert b"did:example:ui-wizard-1" in profile.content
    assert b"python" in profile.content


def test_deployments_honest_registration_history(client):
    _seed(client)
    page = client.get("/ui/deployments")
    assert page.status_code == 200
    assert b"Registration history" in page.content
    assert b"Registered" in page.content
    assert b"Research Agent" in page.content
    assert b"BUILDING" not in page.content
    assert b"no cloud" in page.content.lower()
