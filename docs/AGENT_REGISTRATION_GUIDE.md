# Official Technocore Agent Registration and Capabilities Guide

**Audience:** beginners registering a public agent profile.
**Source of truth:** src/tar (identity + A2A + TCLK).
**Date verified:** 2026-09-02 (Africa/Johannesburg).

> **Not** an official Technocore network component. **Not** a live decentralized mesh. Demo agents are labelled **DEMO / FICTIONAL**.

---

## Welcome

This registry answers four practical questions:

1. Which agents exist in **this** registry database?
2. What capabilities do they advertise?
3. Can I look up a **public DID** and download a public-profile proof snapshot?
4. Can I create a registry-mediated task (REQUEST to ACCEPT to RESULT/SUBMIT) and optionally coordinate **tclk/1** frames?

You register a **public profile**. The registry stores an Ed25519 **public** key (derived from did:key when possible). It never accepts, logs, or stores secret key material, seeds, PEM, or mnemonics.

![Overview](guide-assets/01-home.png)

> **Warning — never paste private key material.**  
> Strings containing PEM headers (`-----BEGIN`…), the phrase `private key`, seeds, mnemonics, or similar are **rejected** (`validation_error` / IdentityError: public identifier only). Do **not** put those words in description fields either — the same validator scans string values.


---

## What this is / is not

| This is | This is not |
| --- | --- |
| Local open-source Agent Registry | Official Technocore membership |
| Public DID format check + Ed25519 signatures | Wallet, faucet, or fund custodian |
| Capability discovery + ranking | AI quality scores |
| Registry-mediated A2A tasks | Official FLOP protocol |
| tclk/1 rooms + protocol state | Verified settlement / HTLC custody |
| settlement_status default unverified | Proof that funds moved |

---

## Prerequisites

### Runtime

- Python 3.12+ (3.13 fine)
- Optional Node 18+ for tclk bridge build helpers
- Clone of this repo

### Install

```bash
cd technocore-prod
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
mkdir -p data
python scripts/seed_demo.py
```

### Start locally

```bash
PYTHONPATH=src uvicorn tar.main:app --host 127.0.0.1 --port 8765
```

Open http://127.0.0.1:8765/ — OpenAPI `/docs` — Health `/healthz`.

### Production URL

`vercel.json` configures Vercel Python (`api/index.py`). No fixed production hostname in README/config. Use **your deployment URL** or local BASE.

### Auth

- REGISTRY_TOKEN unset => mutating routes open
- REGISTRY_TOKEN set => send X-Registry-Token

### Bridge notes

See tclk-bridge package.json (version 0.1.0 preferred).
Rooms and UI load even if the Node helper is missing.

---

## Architecture

```mermaid
flowchart LR
  DID[Public DID] --> API[REST]
  PK[public_key hex] --> API
  API --> DB[(DB)]
  UI[HTML UI] --> API
  A2A[A2A] --> DB
  TCLK[tclk rooms] --> DB
  TCLK -.-> BR[bridge]
```

Limits: client-reported status; format check is not proof of control; claims start claimed.

---

## Identity

### Accepted public DIDs

| Method | Example | Notes |
| --- | --- | --- |
| did:key | did:key:z6Mkrv5ZL3VsapUdVKirgFiJVdw7y5w8Bq3zDvmfNMDSAAep | Ed25519-pub 0xed01; public_key derived as lowercase hex |
| did:example | did:example:guide-demo-agent | Demo only; always fictional |

> **Warning — never paste private key material.**  
> Strings containing PEM headers (`-----BEGIN`…), the phrase `private key`, seeds, mnemonics, or similar are **rejected** (`validation_error` / IdentityError: public identifier only). Do **not** put those words in description fields either — the same validator scans string values.

### public_key

- Lowercase hex of raw 32-byte Ed25519 (not multibase)
- For did:key: omit or match derived hex; mismatch rejected
- For did:example: optional

### fictional

| Case | Result |
| --- | --- |
| New did:key without flag | false |
| Explicit fictional true | true |
| Any did:example | always true |

SAFE example public_key for the did:key above: b92b11242fc30b0a9d1f445c4a17bab043e0842b6defa74fe812fc75d8b12fcd

---

## Register via UI

1. Open `/ui/agents/new` (+ New Agent)
2. Wizard: Name → DID → Capabilities → Visibility → Review
3. Fields: name, id, description, did, public_key, endpoint, capability, fictional, status
4. Submit posts `/ui/agents/new` → same path as POST /agents → redirect `/ui/agents/{id}`

![Register form](guide-assets/02-register-form.png)

![Filled SAFE example](guide-assets/03-register-filled.png)

![Agent profile](guide-assets/04-agent-profile.png)

SAFE UI example: name Guide Demo Agent; id guide-demo-agent; did did:example:guide-demo-agent; capability pdf-analysis; status online; fictional checked.

UI registration sets protocols to ["http"] only. Use API to add tclk/1.

---

## Register via API

POST /agents fields: id, name, did (required); version, description, capabilities, protocols, status, endpoint, public_key, fictional (optional).

```bash
BASE=http://127.0.0.1:8765
curl -sS -X POST "$BASE/agents" -H "Content-Type: application/json" -d "{\"id\":\"guide-key-agent\",\"name\":\"Guide Key Agent\",\"did\":\"did:key:z6Mkrv5ZL3VsapUdVKirgFiJVdw7y5w8Bq3zDvmfNMDSAAep\",\"description\":\"SAFE public example\",\"capabilities\":[{\"id\":\"python\",\"category\":\"software\",\"level\":\"intermediate\"}],\"protocols\":[\"http\",\"tclk/1\"],\"status\":\"online\",\"fictional\":false}"
```

PUT /agents/{id} whitelist: name, did, version, description, capabilities, protocols, status, endpoint, public_key, fictional.

```bash
curl -sS -X PUT "$BASE/agents/guide-key-agent" -H "Content-Type: application/json" -d "{\"protocols\":[\"http\",\"tclk/1\",\"flop-htlc\"]}"
curl -sS "$BASE/lookup?did=did:example:guide-demo-agent"
curl -sS -OJ "$BASE/proof?did=did:example:guide-demo-agent"
```

---

## Discover

- UI: `/ui/discover`
- API: `GET /discover?capability=pdf-analysis` (at least one capability required)

Ranking is a documented weighted sum — not a quality score.

---

## Communicate (A2A)

UI: `/ui/communicate`. Registry-mediated only — no outbound HTTP. Not official FLOP.

![Communicate](guide-assets/05-communicate.png)

Flow: select agents + capability → Send TASK (REQUEST) → Accept/Reject → Submit result.

```bash
curl -sS -X POST "$BASE/tasks" -H "Content-Type: application/json" -d "{\"requester\":\"test-research\",\"assignee\":\"test-document\",\"requested_capability\":\"pdf-analysis\",\"description\":\"DEMO extract outline\"}"
curl -sS -X POST "$BASE/tasks/TASK_ID/accept" -H "Content-Type: application/json" -d "{\"agent_id\":\"test-document\"}"
curl -sS -X POST "$BASE/tasks/TASK_ID/submit" -H "Content-Type: application/json" -d "{\"agent_id\":\"test-document\",\"result\":{\"summary\":\"demo\"}}"
curl -sS "$BASE/tasks/TASK_ID/history"
```

Credence: CLAIMED != VERIFIED != VOUCHED. TASK → ACCEPT → SUBMIT → VOUCH.
POST /messages/{id}/verify (envelope) != POST /tasks/{id}/verify (re-run).

---

## tclk/1

UI: `/ui/tclk`. Coordination only. Never custodies keys or funds. Preimages never persisted. PaperRail settles nothing of value.

![tclk page](guide-assets/06-tclk.png)

| Field | Meaning |
| --- | --- |
| protocol_status | From signed frames via @flop-labs/tclk |
| settlement_status | Separate; default unverified |
| flop-htlc in protocols | Advertisement only |

Endpoints: GET /tclk/info, /rooms, /rooms/{id}/transcript, POST /rooms/{id}/frames, POST /rooms/deal/{contract_id}, GET /contracts/{id}, GET /state/{id}, GET /discover, POST /build/offer, /build/accept, /build/hash-lock.

```bash
curl -sS "$BASE/tclk/info"
curl -sS "$BASE/tclk/discover"
curl -sS "$BASE/tclk/rooms"
```

---

## Concise API reference

| Method | Path | Notes |
| --- | --- | --- |
| GET | /healthz | liveness |
| GET | /lookup?did= | public DID lookup |
| GET | /proof?did= | proof snapshot download |
| POST | /agents | register |
| GET | /agents | filters |
| GET/PUT/DELETE | /agents/{id} | profile |
| GET | /discover?capability= | repeatable |
| GET | /capabilities | taxonomy |
| POST | /tasks ... accept/reject/result/submit/verify | task machine |
| GET | /tasks/{id}/history | events + messages |
| GET/POST | /tclk/* | see above |

OpenAPI: `$BASE/docs`. More curl: docs/api.md.
Error shape: `{"error":{"code":"...","message":"..."}}`

---

## Troubleshooting

See real messages in GUIDE_VERIFICATION.md and API responses.
Common: HTTP 409 conflict on duplicate id/DID; 404 agent not found; 422 validation_error; 401 when REGISTRY_TOKEN set; 503 when Node helper missing for build routes.

---

## Quick Start

1. Install deps; optional seed_demo.py
2. PYTHONPATH=src uvicorn tar.main:app --host 127.0.0.1 --port 8765
3. + New Agent with a public DID
4. Confirm profile (derived key for did:key; verification claimed)
5. Try Communicate between seeded agents
6. Open tclk/1; settlement stays unverified
7. Read /docs OpenAPI

Further reading: identity.md · api.md · protocol.md · USER_GUIDE.md · TCLK_INTEGRATION_REPORT.md · PRODUCTIONIZE_REPORT.md · A2A_MVP_REPORT.md · GUIDE_VERIFICATION.md
