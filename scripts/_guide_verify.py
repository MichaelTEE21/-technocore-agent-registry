"""Register demo agent and exercise key endpoints for the guide."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient
from tar.main import create_app

KNOWN_DID = "did:key:z6Mkrv5ZL3VsapUdVKirgFiJVdw7y5w8Bq3zDvmfNMDSAAep"
KNOWN_PUB = "b92b11242fc30b0a9d1f445c4a17bab043e0842b6defa74fe812fc75d8b12fcd"
SAFE_EXAMPLE_DID = "did:example:guide-demo-agent"

checks = []

def check(name, cond, detail=""):
    checks.append((name, bool(cond), detail))
    print(("OK" if cond else "FAIL"), name, detail)

app = create_app()
with TestClient(app) as client:
    r = client.get("/healthz")
    check("GET /healthz", r.status_code == 200, r.json())

    payload = {
        "id": "guide-key-agent",
        "name": "Guide Key Agent",
        "did": KNOWN_DID,
        "description": "SAFE public example for the registration guide. Public DID only.",
        "capabilities": [
            {"id": "python", "category": "software", "level": "intermediate"},
            {"id": "tokenomics-analysis", "category": "crypto-web3", "level": "intermediate"},
        ],
        "protocols": ["http", "tclk/1"],
        "status": "online",
        "endpoint": "https://example.invalid/agents/guide-key",
        "fictional": False,
    }
    r = client.post("/agents", json=payload)
    if r.status_code == 409:
        r2 = client.get("/agents/guide-key-agent")
        check("POST /agents conflict ok", r2.status_code == 200, "already registered")
        body = r2.json()
    else:
        check("POST /agents 201", r.status_code == 201, r.text[:200])
        body = r.json() if r.status_code == 201 else {}

    if body:
        check("public_key derived", body.get("public_key") == KNOWN_PUB, body.get("public_key"))
        check("fictional false for did:key", body.get("fictional") is False, str(body.get("fictional")))
        check("verification claimed", body.get("verification", {}).get("status") == "claimed")
        check("tclk/1 in protocols", "tclk/1" in (body.get("protocols") or []), str(body.get("protocols")))

    demo = {
        "id": "guide-demo-agent",
        "name": "Guide Demo Agent",
        "did": SAFE_EXAMPLE_DID,
        "description": "Fictional demo agent for screenshots. Public identifier only.",
        "capabilities": [
            {"id": "pdf-analysis", "category": "documents", "level": "intermediate"},
        ],
        "protocols": ["http"],
        "status": "online",
        "fictional": True,
    }
    r = client.post("/agents", json=demo)
    if r.status_code == 409:
        check("demo agent exists", True, "409")
        body_d = client.get("/agents/guide-demo-agent").json()
        check("demo always fictional", body_d.get("fictional") is True)
    else:
        check("demo agent create", r.status_code == 201, r.text[:200])
        if r.status_code == 201:
            check("demo always fictional", r.json().get("fictional") is True)

    bad = dict(demo)
    bad["id"] = "bad-key"
    bad["did"] = "-----BEGIN PRIVATE KEY-----abc"
    r = client.post("/agents", json=bad)
    check("reject PEM paste", r.status_code in (400, 422), r.text[:180])

    # description containing forbidden phrase rejected
    bad2 = dict(demo)
    bad2["id"] = "bad-desc"
    bad2["did"] = "did:example:bad-desc"
    bad2["description"] = "contains private key wording"
    r = client.post("/agents", json=bad2)
    check("reject private key phrase in description", r.status_code in (400, 422), r.text[:180])

    for path in ["/", "/ui/agents/new", "/ui/agents/guide-demo-agent", "/ui/communicate", "/ui/tclk", "/ui/discover"]:
        rr = client.get(path)
        check(f"UI {path}", rr.status_code == 200, f"status={rr.status_code} len={len(rr.text)}")

    html = client.get("/ui/agents/new").text
    for field in [
        'name="name"', 'name="id"', 'name="did"', 'name="public_key"',
        'name="endpoint"', 'name="fictional"', 'name="status"',
        'name="capability"', 'name="description"',
    ]:
        check(f"form field {field}", field in html)

    info = client.get("/tclk/info")
    check("GET /tclk/info", info.status_code == 200, str(info.json())[:240])
    check("tclk settlement unverified default", info.json().get("settlement") == "unverified_by_default")
    check("tclk custody false", info.json().get("custody") is False)
    disc = client.get("/tclk/discover")
    check("GET /tclk/discover", disc.status_code == 200, f"items={len(disc.json().get('items', []))}")

    agents = client.get("/agents").json()
    check("agents listed", agents.get("count", 0) >= 1, str(agents.get("count")))

    put = client.put("/agents/guide-key-agent", json={"protocols": ["http", "tclk/1", "flop-htlc"]})
    check("PUT protocols", put.status_code == 200, str(put.json().get("protocols")))

    miss = client.get("/agents/no-such-agent-xyz")
    check("404 agent message", miss.status_code == 404 and "not found" in miss.text.lower(), miss.text[:160])

    # UI form POST registration (demo)
    form = {
        "name": "UI Form Demo",
        "id": "ui-form-demo",
        "did": "did:example:ui-form-demo",
        "description": "Registered via UI form path",
        "endpoint": "",
        "public_key": "",
        "status": "online",
        "fictional": "true",
        "capability": "python",
    }
    r = client.post("/ui/agents/new", data=form, follow_redirects=False)
    check("UI form POST redirect", r.status_code in (303, 302), f"status={r.status_code} loc={r.headers.get('location')}")

print("\n=== SUMMARY ===")
fails = [c for c in checks if not c[1]]
print(f"{len(checks)-len(fails)}/{len(checks)} passed")
for name, ok, detail in fails:
    print("FAIL", name, detail)
Path("docs/GUIDE_VERIFICATION.md").write_text(
    "# Guide verification checklist\n\n"
    "Generated by scripts/_guide_verify.py against the live TestClient (lifespan + SQLite).\n\n"
    + "\n".join(f"- [{'x' if ok else ' '}] {name}" + (f" — {detail}" if detail and not ok else "") for name, ok, detail in checks)
    + f"\n\n**Result:** {len(checks)-len(fails)}/{len(checks)} passed.\n"
)
print("Wrote docs/GUIDE_VERIFICATION.md")
sys.exit(1 if fails else 0)
