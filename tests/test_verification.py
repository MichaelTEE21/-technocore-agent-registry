from tests.conftest import AGENT_A


def test_post_verification_does_not_auto_verify(client):
    assert client.post("/agents", json=AGENT_A).status_code == 201
    resp = client.post(
        "/agents/test-research/verification",
        json={
            "kind": "evidence",
            "summary": "Public write-up of research method.",
            "evidence_uri": "https://example.invalid/evidence/1",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["current_status"] == "claimed"
    kinds = {i["kind"] for i in body["items"]}
    assert "evidence" in kinds
    assert all(i["status"] != "verified" for i in body["items"] if i["kind"] == "evidence")


def test_dispute(client):
    client.post("/agents", json=AGENT_A)
    resp = client.post(
        "/agents/test-research/verification",
        json={"kind": "dispute", "summary": "Capability overclaimed."},
    )
    assert resp.status_code == 201
    assert resp.json()["current_status"] == "disputed"
