from tests.conftest import AGENT_A


def test_auth_open_when_token_unset(client):
    resp = client.post("/agents", json=AGENT_A)
    assert resp.status_code == 201


def test_auth_required_when_token_set(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from tar import config as cfg
    from tar import db as dbmod
    from tar import main as mainmod

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'auth.db'}")
    monkeypatch.setenv("REGISTRY_TOKEN", "demo-token")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "10000")
    settings = cfg.load_settings()
    monkeypatch.setattr(cfg, "settings", settings)
    dbmod.reset_engine(settings.database_url)
    app = mainmod.create_app()
    app.state.settings = settings
    with TestClient(app) as client:
        denied = client.post("/agents", json=AGENT_A)
        assert denied.status_code == 401
        ok = client.post("/agents", json=AGENT_A, headers={"X-Registry-Token": "demo-token"})
        assert ok.status_code == 201
        listed = client.get("/agents")
        assert listed.status_code == 200


def test_payload_too_large(client):
    huge = dict(AGENT_A)
    huge["id"] = "big"
    huge["did"] = "did:example:big"
    huge["description"] = "x" * 80_000
    resp = client.post("/agents", json=huge)
    assert resp.status_code in {413, 422}
