import json

from tests.conftest import AGENT_B

PEM = "-----BEGIN PRIVATE KEY-----\nMIGHAoGBADEMO\n-----END PRIVATE KEY-----"


def test_lookup_registered_demo_did(client):
    created = client.post("/agents", json=AGENT_B)
    assert created.status_code == 201, created.text
    resp = client.get("/lookup", params={"did": "did:example:test-document"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["found"] is True
    assert body["format"] == "ok"
    assert body["did"] == "did:example:test-document"
    assert body["agent"]["id"] == "test-document"
    ids = {c["id"] for c in body["capabilities"]}
    assert "pdf-analysis" in ids
    assert "document-extraction" in ids
    for cap in body["capabilities"]:
        assert "id" in cap and "category" in cap and "level" in cap and "evidence_status" in cap


def test_lookup_unknown_valid_did(client):
    resp = client.get("/lookup", params={"did": "did:example:not-registered-xyz"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["found"] is False
    assert body["format"] == "ok"
    assert body["did"] == "did:example:not-registered-xyz"
    assert body["agent"] is None
    assert body["capabilities"] == []
    assert "not in this local registry" in body["message"]


def test_lookup_invalid_pem_and_private(client):
    invalid = client.get("/lookup", params={"did": "not-a-did"})
    assert invalid.status_code == 400
    pem = client.get("/lookup", params={"did": PEM})
    assert pem.status_code == 400
    pem_body = pem.json()
    blob = json.dumps(pem_body).lower()
    assert "begin private" not in blob
    assert "migh" not in blob
    private = client.get("/lookup", params={"did": "private"})
    assert private.status_code == 400
    proof_pem = client.get("/proof", params={"did": PEM})
    assert proof_pem.status_code == 400


def test_proof_registered_agent_is_public_snapshot(client):
    client.post("/agents", json=AGENT_B)
    resp = client.get("/proof", params={"did": "did:example:test-document"})
    assert resp.status_code == 200, resp.text
    disp = resp.headers.get("content-disposition", "")
    assert "attachment" in disp
    assert "proof-test-document.json" in disp
    body = resp.json()
    assert body["type"] == "tar.proof.profile.v1"
    assert body["found"] is True
    assert body["did"] == "did:example:test-document"
    assert body["agent_id"] == "test-document"
    assert body["name"]
    assert body["content_hash"].startswith("sha256:")
    assert len(body["content_hash"]) == len("sha256:") + 64
    assert "private_key" not in body
    assert "secret" not in body
    blob = json.dumps(body).lower()
    assert "-----begin" not in blob
    assert "private_key" not in blob
    assert "mnemonic" not in blob
    ids = {c["id"] for c in body["capabilities"]}
    assert "pdf-analysis" in ids
    for cap in body["capabilities"]:
        assert set(cap) >= {"id", "category", "level", "evidence_status"}
    from tar.proof import hash_public_fields

    fields = {
        "did": body["did"],
        "found": body["found"],
        "agent_id": body["agent_id"],
        "name": body["name"],
        "capabilities": body["capabilities"],
        "verification": body["verification"],
        "public_key": body["public_key"],
    }
    assert body["content_hash"] == hash_public_fields(fields)
    events = client.get(
        "/contributions", params={"agent": "test-document", "event": "profile_proof_generated"}
    )
    assert events.status_code == 200
    assert events.json()["count"] >= 1
    alias = client.get("/agents/test-document/proof")
    assert alias.status_code == 200
    assert alias.json()["type"] == "tar.proof.profile.v1"


def test_proof_unregistered_valid_did(client):
    resp = client.get("/proof", params={"did": "did:example:not-registered-xyz"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["type"] == "tar.proof.profile.v1"
    assert body["found"] is False
    assert body["did"] == "did:example:not-registered-xyz"
    assert body["agent_id"] is None
    assert body["content_hash"].startswith("sha256:")
    disp = resp.headers.get("content-disposition", "")
    assert "attachment" in disp


def test_home_search_by_did(client):
    client.post("/agents", json=AGENT_B)
    home = client.get("/", params={"q": "did:example:test-document"})
    assert home.status_code == 200
    assert b"Document Agent" in home.content
    substring = client.get("/", params={"q": "example:test-document"})
    assert substring.status_code == 200
    assert b"Document Agent" in substring.content


def test_ui_lookup_shows_capabilities_and_proof_link(client):
    client.post("/agents", json=AGENT_B)
    page = client.get("/ui/lookup", params={"did": "did:example:test-document"})
    assert page.status_code == 200
    assert b"pdf-analysis" in page.content
    assert b"What they can do" in page.content
    assert b"Generate proof" in page.content
    home = client.get("/")
    assert b"Paste a public DID" in home.content
