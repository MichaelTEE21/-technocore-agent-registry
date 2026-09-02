"""tclk/1 integration: bridge, rooms, discovery, protocol vs settlement."""

from __future__ import annotations

import json
import time

import pytest

from tar.tclk import redact_secrets
from tar.tclk_bridge import TclkBridgeError, ping

PAYER_DID = "did:key:z6Mkrv5ZL3VsapUdVKirgFiJVdw7y5w8Bq3zDvmfNMDSAAep"
# Second well-known did:key from productionize tests companion
PAYEE_DID = "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK"


def _bridge_available() -> bool:
    try:
        ping()
        return True
    except TclkBridgeError:
        return False


pytestmark = pytest.mark.skipif(
    not _bridge_available(),
    reason="tclk-bridge / node / @flop-labs/tclk not available",
)


def test_bridge_ping():
    info = ping()
    assert info["version"] == "tclk/1"
    assert info["offerRoom"] == "tclk-offers"


def test_redact_secrets_never_keeps_preimage():
    blob = {"type": "reveal", "secret": "0x" + "ab" * 32, "nested": {"preimage": "0xdead"}}
    out = redact_secrets(blob)
    assert out["secret"] == "[REDACTED]"
    assert out["nested"]["preimage"] == "[REDACTED]"


def test_tclk_info_and_ui(client):
    resp = client.get("/tclk/info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["protocol"] == "tclk/1"
    assert body["custody"] is False
    assert "unverified" in body["settlement"]
    assert body["bridge"] is not None

    ui = client.get("/ui/tclk")
    assert ui.status_code == 200
    assert b"PROTOCOL VS SETTLEMENT" in ui.content
    assert b"unverified" in ui.content.lower()


def test_discover_advertising(client):
    agent = {
        "id": "tclk-payer-demo",
        "name": "TCLK Payer Demo",
        "did": PAYER_DID,
        "description": "FICTIONAL agent advertising tclk/1 + flop-htlc.",
        "capabilities": [
            {"id": "crypto-research", "category": "crypto-web3", "level": "advanced"}
        ],
        "protocols": ["http", "tclk/1", "flop-htlc"],
        "status": "online",
        "fictional": True,
    }
    assert client.post("/agents", json=agent).status_code == 201
    disc = client.get("/tclk/discover")
    assert disc.status_code == 200
    ids = [i["agent"]["id"] for i in disc.json()["items"]]
    assert "tclk-payer-demo" in ids


def test_offer_room_transcript_and_state(client):
    # Build offer via bridge API
    now = int(time.time() * 1000)
    built = client.post(
        "/tclk/build/offer",
        json={
            "fields": {
                "from": PAYER_DID,
                "role": "payer",
                "lock": "hash",
                "amount": "1000000",
                "asset": "FLOP",
                "rails": ["flop-htlc", "paper"],
                "claimByMs": now + 3_600_000,
                "refundAfterMs": now + 7_200_000,
                "expiresMs": now + 600_000,
            }
        },
    )
    assert built.status_code == 200, built.text
    offer = built.json()["offer"]
    assert offer["type"] == "offer"
    assert offer["id"].startswith("0x")

    posted = client.post(
        "/tclk/rooms/tclk-offers/frames",
        json={"room_id": "tclk-offers", "frame": offer},
    )
    assert posted.status_code == 201, posted.text
    entry = posted.json()
    assert entry["frame_type"] == "offer"
    assert entry["signature_status"] in {"unsigned", "no_key", "valid", "invalid"}
    assert "[REDACTED]" not in json.dumps(entry["frame"]) or "secret" not in entry["frame"]

    rooms = client.get("/tclk/rooms")
    assert rooms.status_code == 200
    assert any(r["id"] == "tclk-offers" for r in rooms.json()["items"])

    transcript = client.get("/tclk/rooms/tclk-offers/transcript")
    assert transcript.status_code == 200
    assert len(transcript.json()["items"]) >= 1

    # Contract keyed by offer:… until accept
    state = client.get(f"/tclk/contracts/offer:{offer['id']}")
    assert state.status_code == 200
    body = state.json()
    assert body["protocol_status"] == "proposed"
    assert body["settlement_status"] == "unverified"
    assert body["paper_only"] is True
    assert "secret" not in (body.get("state") or {})


def test_accept_advances_protocol_not_settlement(client):
    now = int(time.time() * 1000)
    offer_resp = client.post(
        "/tclk/build/offer",
        json={
            "fields": {
                "from": PAYER_DID,
                "role": "payer",
                "lock": "hash",
                "amount": "42",
                "asset": "FLOP",
                "rails": ["paper"],
                "claimByMs": now + 3_600_000,
                "refundAfterMs": now + 7_200_000,
                "expiresMs": now + 600_000,
            }
        },
    )
    offer = offer_resp.json()["offer"]
    assert client.post("/tclk/rooms/tclk-offers/frames", json={"frame": offer}).status_code == 201

    lock = client.post("/tclk/build/hash-lock")
    assert lock.status_code == 200
    assert "preimage" in lock.json()
    assert "hash" in lock.json()
    # Client holds preimage; registry must not require storing it
    statement = lock.json()["hash"]

    accept_resp = client.post(
        "/tclk/build/accept",
        json={"offer": offer, "accept": {"from": PAYEE_DID, "statement": statement}},
    )
    assert accept_resp.status_code == 200, accept_resp.text
    accept = accept_resp.json()["accept"]
    assert accept["contract"].startswith("0x")

    posted = client.post(
        "/tclk/rooms/tclk-offers/frames",
        json={"frame": accept},
    )
    assert posted.status_code == 201, posted.text

    st = client.get(f"/tclk/state/{accept['contract']}")
    assert st.status_code == 200
    body = st.json()
    assert body["protocol_status"] == "accepted"
    assert body["settlement_status"] == "unverified"
    assert "secret" not in json.dumps(body)

    # Reveal frame with secret must store redacted only
    reveal = {
        "type": "reveal",
        "from": PAYEE_DID,
        "contract": accept["contract"],
        "secret": lock.json()["preimage"],
    }
    # Need lock frame first for machine — skip full path; just ensure redaction on post
    # Posting reveal before lock should still redact stored JSON
    deal = client.post(f"/tclk/rooms/deal/{accept['contract']}")
    assert deal.status_code == 201
    room_id = deal.json()["id"]
    rev = client.post(f"/tclk/rooms/{room_id}/frames", json={"frame": reveal})
    assert rev.status_code == 201
    stored = rev.json()["frame"]
    assert stored.get("secret") == "[REDACTED]"
