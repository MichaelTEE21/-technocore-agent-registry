"""Productionize coverage: did:key pubkey, fictional defaults, PUT metadata, proofs."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tar.crypto import (
    SignatureError,
    canonical_message_bytes,
    ed25519_public_key_from_did_key,
    generate_keypair,
    public_key_hex,
    resolve_registration_public_key,
    resolve_verify_key,
    sign,
)
from tar.identity import DidKeyIdentityProvider, IdentityError, default_identity_provider

# Well-known Ed25519 did:key (public only). Matches docs known agent DID.
KNOWN_DID = "did:key:z6Mkrv5ZL3VsapUdVKirgFiJVdw7y5w8Bq3zDvmfNMDSAAep"
KNOWN_PUB_HEX = "b92b11242fc30b0a9d1f445c4a17bab043e0842b6defa74fe812fc75d8b12fcd"
W3C_DID = "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK"


def test_valid_did_key_extracts_pubkey():
    raw = ed25519_public_key_from_did_key(KNOWN_DID)
    assert len(raw) == 32
    assert raw.hex() == KNOWN_PUB_HEX
    assert DidKeyIdentityProvider().extract_public_key_hex(KNOWN_DID) == KNOWN_PUB_HEX
    assert DidKeyIdentityProvider().validate_public_did(W3C_DID) == W3C_DID


def test_malformed_did_rejected():
    provider = DidKeyIdentityProvider()
    with pytest.raises(IdentityError):
        provider.validate_public_did("did:key:z")
    with pytest.raises(IdentityError):
        provider.validate_public_did("did:key:not-base58!!!")
    with pytest.raises(IdentityError):
        default_identity_provider.validate_public_did("did:web:example.com")
    with pytest.raises(SignatureError):
        ed25519_public_key_from_did_key("did:example:test-research")


def test_pubkey_mismatch_rejected():
    wrong = "aa" * 32
    with pytest.raises(SignatureError):
        resolve_registration_public_key(KNOWN_DID, wrong)
    assert resolve_registration_public_key(KNOWN_DID, KNOWN_PUB_HEX) == KNOWN_PUB_HEX
    assert resolve_registration_public_key(KNOWN_DID, None) == KNOWN_PUB_HEX


def test_create_agent_derives_pubkey_and_non_demo_default(client):
    payload = {
        "id": "mananze-technocore-agent",
        "name": "Mananze Technocore Agent",
        "did": KNOWN_DID,
        "description": "Independent open-source registration. Not official Technocore membership.",
        "capabilities": [
            {"id": "python", "category": "software", "level": "advanced"},
        ],
        "protocols": ["http"],
        "status": "online",
        "endpoint": "https://example.invalid/agents/mananze",
    }
    resp = client.post("/agents", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["public_key"] == KNOWN_PUB_HEX
    assert body["fictional"] is False
    assert body["verification"]["status"] == "claimed"
    assert body["endpoint"] == "https://example.invalid/agents/mananze"


def test_demo_fictional_create(client):
    payload = {
        "id": "test-demo-flag",
        "name": "Demo Flag Agent",
        "did": "did:example:test-demo-flag",
        "capabilities": [],
        "protocols": ["http"],
    }
    resp = client.post("/agents", json=payload)
    assert resp.status_code == 201, resp.text
    assert resp.json()["fictional"] is True

    payload2 = {
        "id": "test-explicit-fiction",
        "name": "Explicit Fiction",
        "did": W3C_DID,
        "fictional": True,
        "capabilities": [],
        "protocols": ["http"],
    }
    resp2 = client.post("/agents", json=payload2)
    assert resp2.status_code == 201, resp2.text
    assert resp2.json()["fictional"] is True
    assert resp2.json()["public_key"]


def test_put_metadata_whitelist(client):
    assert (
        client.post(
            "/agents",
            json={
                "id": "upd-target",
                "name": "Before",
                "did": "did:example:upd-target",
                "capabilities": [],
                "protocols": ["http"],
                "endpoint": "https://example.invalid/before",
            },
        ).status_code
        == 201
    )
    upd = client.put(
        "/agents/upd-target",
        json={
            "name": "After",
            "description": "Updated public blurb",
            "version": "2.0.0",
            "status": "busy",
            "protocols": ["http", "a2a"],
            "endpoint": "https://example.invalid/after",
            "unknownFuture": {"x": 1},
            "fictional": True,
        },
    )
    assert upd.status_code == 200, upd.text
    body = upd.json()
    assert body["name"] == "After"
    assert body["description"] == "Updated public blurb"
    assert body["version"] == "2.0.0"
    assert body["status"] == "busy"
    assert body["protocols"] == ["http", "a2a"]
    assert body["endpoint"] == "https://example.invalid/after"
    assert "unknownFuture" not in body
    secret = client.put(
        "/agents/upd-target",
        json={"name": "Nope", "private_key": "aa" * 32},
    )
    assert secret.status_code == 422


def test_put_invalid_endpoint(client):
    client.post(
        "/agents",
        json={
            "id": "bad-ep",
            "name": "Bad EP",
            "did": "did:example:bad-ep",
            "capabilities": [],
            "protocols": ["http"],
        },
    )
    bad = client.put("/agents/bad-ep", json={"endpoint": "ftp://not-allowed.example"})
    assert bad.status_code == 422
    clear = client.put("/agents/bad-ep", json={"endpoint": ""})
    assert clear.status_code == 200
    assert clear.json()["endpoint"] is None


def test_put_did_recomputes_public_key(client):
    client.post(
        "/agents",
        json={
            "id": "rekey",
            "name": "Rekey",
            "did": "did:example:rekey",
            "capabilities": [],
            "protocols": ["http"],
            "fictional": True,
        },
    )
    upd = client.put("/agents/rekey", json={"did": KNOWN_DID, "fictional": False})
    assert upd.status_code == 200, upd.text
    assert upd.json()["did"] == KNOWN_DID
    assert upd.json()["public_key"] == KNOWN_PUB_HEX
    assert upd.json()["fictional"] is False


def test_put_rejects_pubkey_mismatch(client):
    client.post(
        "/agents",
        json={
            "id": "mismatch",
            "name": "Mismatch",
            "did": KNOWN_DID,
            "capabilities": [],
            "protocols": ["http"],
        },
    )
    bad = client.put("/agents/mismatch", json={"public_key": "bb" * 32})
    assert bad.status_code == 400


def test_proof_verify_uses_registered_public_key(client):
    priv, pub = generate_keypair()
    pub_hex = public_key_hex(pub)
    a = {
        "id": "sig-a",
        "name": "Sig A",
        "did": "did:example:sig-a",
        "public_key": pub_hex,
        "capabilities": [
            {"id": "crypto-research", "category": "crypto-web3", "level": "advanced"},
        ],
        "protocols": ["http"],
        "status": "online",
        "fictional": True,
    }
    b = {
        "id": "sig-b",
        "name": "Sig B",
        "did": "did:example:sig-b",
        "capabilities": [
            {"id": "pdf-analysis", "category": "documents", "level": "advanced"},
        ],
        "protocols": ["http"],
        "status": "online",
        "fictional": True,
    }
    assert client.post("/agents", json=a).status_code == 201
    assert client.post("/agents", json=b).status_code == 201
    assert resolve_verify_key(a["did"], pub_hex) == pub

    created = client.post(
        "/tasks",
        json={
            "requester": "sig-b",
            "assignee": "sig-a",
            "requested_capability": "crypto-research",
            "description": "proof flow",
        },
    )
    assert created.status_code == 201
    task_id = created.json()["task_id"]
    ts = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    mid = "msg-prod-accept"
    payload = {"ok": True}
    sig = sign(
        priv,
        canonical_message_bytes(
            message_id=mid,
            type="ACCEPT",
            from_agent="sig-a",
            to_agent="sig-b",
            timestamp=ts,
            task_id=task_id,
            payload=payload,
        ),
    )
    ok = client.post(
        f"/tasks/{task_id}/accept",
        json={
            "agent_id": "sig-a",
            "message_id": mid,
            "timestamp": ts,
            "signature": sig,
            "payload": payload,
        },
    )
    assert ok.status_code == 200, ok.text

    ver = client.post(
        "/agents/sig-a/verification",
        json={"kind": "evidence", "summary": "blog post", "capability_id": "crypto-research"},
    )
    assert ver.status_code == 201
    assert ver.json()["current_status"] == "claimed"
    check = client.post(
        "/agents/sig-a/verification",
        json={
            "kind": "independently-checked",
            "summary": "re-ran",
            "capability_id": "crypto-research",
            "checker_id": "sig-b",
        },
    )
    assert check.status_code == 201
    assert check.json()["current_status"] == "independently-checked"
    vouch = client.post(
        "/agents/sig-a/verification",
        json={
            "kind": "vouch",
            "summary": "vouched after check",
            "capability_id": "crypto-research",
            "checker_id": "sig-b",
        },
    )
    assert vouch.status_code == 201
    assert vouch.json()["current_status"] == "vouched"
    profile = client.get("/agents/sig-a").json()
    cap = next(c for c in profile["capabilities"] if c["id"] == "crypto-research")
    assert cap["evidence_status"] == "community-verified"


def test_rejects_key_material_on_create(client):
    resp = client.post(
        "/agents",
        json={
            "id": "evil-pem",
            "name": "Evil",
            "did": "-----BEGIN PRIVATE KEY-----\nMIGH\n-----END PRIVATE KEY-----",
            "capabilities": [],
            "protocols": ["http"],
        },
    )
    assert resp.status_code == 422


def test_sqlite_agent_roundtrip(client):
    """Portable SQLAlchemy paths under SQLite (same models as Neon)."""
    resp = client.post(
        "/agents",
        json={
            "id": "sqlite-ok",
            "name": "SQLite OK",
            "did": KNOWN_DID,
            "capabilities": [
                {"id": "testing", "category": "software", "level": "intermediate"},
            ],
            "protocols": ["http"],
            "endpoint": "https://example.invalid/sqlite",
        },
    )
    assert resp.status_code == 201
    got = client.get("/agents/sqlite-ok")
    assert got.status_code == 200
    assert got.json()["public_key"] == KNOWN_PUB_HEX
    listed = client.get("/agents", params={"capability": "testing"})
    assert any(a["id"] == "sqlite-ok" for a in listed.json()["items"])


def test_ui_agent_profile_shows_pubkey_and_flags(client):
    client.post(
        "/agents",
        json={
            "id": "ui-agent",
            "name": "UI Agent",
            "did": KNOWN_DID,
            "capabilities": [],
            "protocols": ["http"],
            "endpoint": "https://example.invalid/ui",
        },
    )
    page = client.get("/ui/agents/ui-agent")
    assert page.status_code == 200
    text = page.text
    assert KNOWN_PUB_HEX in text
    assert "https://example.invalid/ui" in text
    assert "Non-demo registration" in text
    assert "did:key" in text
