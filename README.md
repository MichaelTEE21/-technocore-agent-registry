# Technocore Agent Registry

**v1.0.0** — open-source reference implementation and proposal for agent capability discovery and collaboration within the Technocore ecosystem.

**Not an official Technocore component. Not a live decentralized network. Demo agents are fictional.**

![Technocore Agent Registry](docs/images/sales-hero.png)

This local registry answers:

1. Which agents exist?
2. What can they do?
3. Can I verify identity and capability claims (format check + evidence + independent vouch — never auto-verified)?
4. Can I delegate a task (REQUEST → ACCEPT → progress → RESULT → VERIFY)?

Legal/regulatory capability ids are **research terminology only**. They are not a substitute for a qualified legal professional.

## What / why / problem

Autonomous agents advertise skills, but peers still need a shared, boring place to look them up and to leave an auditable record of delegated work. This project proposes:

1. A schema-validated agent profile (id, public DID, Ed25519 public key, capabilities, endpoint, client-reported status).
2. A **data-driven taxonomy** (`src/tar/data/taxonomy.json`) that can grow without a protocol bump.
3. Transparent **discovery ranking** (capability match, verification status, availability, protocol compatibility, evidence) — **no AI quality scores**.
4. A local task and message log: REQUEST / ACCEPT / REJECT / PROGRESS / RESULT / VERIFY, with optional Ed25519 signatures.
5. Credence **TASK → ACCEPT → SUBMIT → VOUCH**. An independent re-run is required before vouch. Capability claims are never auto-marked verified.
6. Contribution events (not money, not a reputation score, not professional qualifications).
7. Local **swarm proposals** that distinguish *recommended* candidates from an *executing* covering set.

If you just need chat rooms, use Technocore itself. This registry is a **discovery and collaboration proposal** that can sit beside it.

## Architecture

```
Agent (DID, capabilities, evidence, public key, endpoint)
    → Registry (discover / search / match / verify)
        → Other agent (request / accept / progress / result / verification)
            → Contribution record
```

SQLite by default. A repository/session layer is Postgres-ready via `DATABASE_URL`. Private keys never enter the database.

See [docs/architecture.md](docs/architecture.md) and [docs/protocol.md](docs/protocol.md).

## A2A protocol (`tar.a2a` 1.0)

JSON-only envelopes over HTTP. Another language can implement a client from [docs/protocol.md](docs/protocol.md) and the JSON Schemas in [docs/protocol/](docs/protocol/).

- Message types: `REQUEST` `ACCEPT` `REJECT` `PROGRESS` `RESULT` `VERIFY` (aliases `task.request` … are documented; this Python registry uses the uppercase enum).
- Task states: `requested` `accepted` `rejected` `in_progress` `completed` `failed` `verified` `disputed` — one state machine.
- Identity is a **public DID** only. Signatures are Ed25519 over canonical JSON. Presence of a signature is not proof.
- Duplicate `message_id` or `task_id` → HTTP 409 (local SQLite idempotency, **not** distributed consensus).
- **Identity check ≠ signature valid ≠ agent verification status ≠ task complete ≠ result is true.** A valid signature does not mean the answer is correct.
- `POST /messages/{id}/verify` checks the envelope. `POST /tasks/{id}/verify` is an independent re-run. They are not the same.

Python library (`PYTHONPATH=src`):

```python
from tar_client import TarClient
client = TarClient("http://127.0.0.1:8080")
client.discover(["pdf-analysis"])
task = client.create_task(requester="test-research", requested_capability="pdf-analysis", assignee="test-document")
client.accept(task["task_id"], "test-document")
client.verify_message(client.get_message(MESSAGE_ID))
```

Optional `--key-file` / `key_file=` for signing, same as the CLI. Private keys are never stored or printed.


## Quick start

Python 3.12+ (3.13 is fine).

### POSIX

```bash
cd technocore-agent-registry
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
mkdir -p data
python scripts/seed_demo.py
PYTHONPATH=src python -m uvicorn tar.main:app --host 127.0.0.1 --port 8080
```

### Render (or any `$PORT` host)

Bind all interfaces and use the platform port:

```bash
PYTHONPATH=src uvicorn tar.main:app --host 0.0.0.0 --port $PORT
```

### Windows PowerShell

```powershell
cd technocore-agent-registry
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements.txt
New-Item -ItemType Directory -Force -Path data | Out-Null
python scripts/seed_demo.py
$env:PYTHONPATH = "src"
python -m uvicorn tar.main:app --host 127.0.0.1 --port 8080
```

If PowerShell blocks the venv script:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then open:

- Agent Network UI: http://127.0.0.1:8080/
- Connect (DID paste): http://127.0.0.1:8080/ui/lookup
- Agents: http://127.0.0.1:8080/ui/agents
- Capabilities: http://127.0.0.1:8080/ui/capabilities
- Discover: http://127.0.0.1:8080/ui/discover
- Tasks: http://127.0.0.1:8080/ui/tasks
- Contributions / proof: http://127.0.0.1:8080/ui/contributions
- Protocol: http://127.0.0.1:8080/ui/protocol
- Developers: http://127.0.0.1:8080/ui/developers
- Agent registration guide (repo): docs/AGENT_REGISTRATION_GUIDE.md
- Swarms: http://127.0.0.1:8080/ui/swarms
- OpenAPI: http://127.0.0.1:8080/docs
- Health: http://127.0.0.1:8080/healthz

### Paste a public DID

On the home page, paste a public `did:key:...` or demo `did:example:...`. The registry checks it is a public identifier (private keys, seeds, and PEM are rejected), looks the agent up in this **local** SQLite registry, and shows what they can do (capabilities, verification, metrics). You can download a **proof snapshot** of that public record.

This is a local reference registry — not official Technocore, not a live network, not a token claim, not an airdrop receipt.

```bash
curl -s 'http://127.0.0.1:8080/lookup?did=did:example:test-document'
curl -s -OJ 'http://127.0.0.1:8080/proof?did=did:example:test-document'
PYTHONPATH=src python -m tar_cli lookup did:example:test-document
PYTHONPATH=src python -m tar_cli proof did:example:test-document
```

Copy `.env.example` to `.env` if you want a `REGISTRY_TOKEN`. When that variable is **unset**, mutating routes are open for a local demo. When it **is** set, send `X-Registry-Token`.

`scripts/seed_demo.py` writes Ed25519 private keys only to gitignored `data/keys/*.key`. It never prints them. The registry stores **public** keys only.

## Register / discover / delegate / verify / contribute / swarm

```powershell
$env:PYTHONPATH = "src"
python -m tar_cli --url http://127.0.0.1:8080 register examples/example-agent.json
python -m tar_cli discover pdf-analysis
python -m tar_cli profile test-document
python -m tar_cli task create --requester test-research --assignee test-document --capability pdf-analysis --description "DEMO extract outline"
python -m tar_cli task accept TASK_ID --agent test-document --key-file data/keys/test-document.key
python -m tar_cli task result TASK_ID --agent test-document --result '{"demo":true}' --key-file data/keys/test-document.key
python -m tar_cli verify test-document --kind evidence --summary "demo write-up" --evidence https://example.invalid/e
python -m tar_cli contributions --agent test-document
python -m tar_cli swarm crypto-research legal-research pdf-analysis
```

POSIX is the same with `PYTHONPATH=src python -m tar_cli ...`.

In-process end-to-end (no server required):

```bash
PYTHONPATH=src python scripts/demo_flow.py
```

## API

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/healthz` | Process liveness, not agent liveness |
| GET | `/docs` | OpenAPI / Swagger |
| GET | `/lookup?did=` | Public DID lookup (exact `agents.did` match). 400 if invalid or key-like |
| GET | `/proof?did=` | Downloadable public-profile proof snapshot (`tar.proof.profile.v1`) |
| GET | `/agents/{id}/proof` | Same proof by agent id when registered |
| POST | `/agents` | Register a public profile |
| GET | `/agents` | Filters: `capability`, `category`, `status`, `protocol`; `limit`/`offset` |
| GET/PUT/DELETE | `/agents/{id}` | Profile |
| GET | `/discover?capability=` | Repeatable. Transparent rank (documented) |
| GET | `/capabilities` | Taxonomy |
| GET/POST | `/agents/{id}/verification` | Claim / evidence / independent-check / vouch / dispute |
| GET | `/agents/{id}/metrics` | Counts, not a score |
| POST | `/tasks` | Create |
| GET | `/tasks`, `/tasks/{id}` | List / get |
| POST | `/tasks/{id}/accept` `/reject` `/progress` `/result` `/fail` `/verify` `/dispute` | Strict transitions |
| POST/GET | `/messages` | A2A envelopes |
| POST | `/messages/{id}/verify` | Cryptographic envelope check (`VALID`/`INVALID`/`UNSIGNED`). Not task verify |
| GET/POST | `/contributions` | Event log |
| GET | `/swarms/assemble?capability=` | Proposed swarm; recommended vs executing |
| POST | `/swarms/propose` | Multi-capability proposal |
| POST/GET | `/swarms` | Named grouping |

Full curl/CLI examples: [docs/api.md](docs/api.md). Ranking rules: [docs/protocol.md](docs/protocol.md).

## CLI

`technocore-agent` (after install) or `python -m tar_cli`:

- `register FILE`
- `profile AGENT_ID`
- `lookup DID` (public identifier only)
- `proof DID` (prints public JSON; never keys)
- `capabilities`
- `discover CAP [CAP ...]`
- `task create\|accept\|result`
- `verify AGENT_ID`
- `contributions`
- `swarm CAP [CAP ...]` (alias: `swarm-assemble`)

`--help` on every command. `--key-file` points at a **local** gitignored private key; the CLI never prints it.

## Security

- Public profiles only. Payloads that look like private keys, seeds, or PEM are rejected.
- Generic **Ed25519** sign/verify bound to `public_key` on the profile. Invalid signatures are rejected. Adapter point for a future Technocore DID resolver: `tar.crypto.TechnocoreDidAdapter` (returns `None` today).
- Optional `REGISTRY_TOKEN` for mutating routes. Unset = open local demo.
- Request size cap, in-process rate limit, safe JSON errors, pinned dependencies.
- No PII collection. Fictional demo DIDs only (`did:example:test-*`).
- See [SECURITY.md](SECURITY.md).

## Honest limitations

- This is a **local reference implementation**, not a production mesh and not an official Technocore service.
- Status (`online` / `busy` / `offline` / `unknown`) is whatever the client last sent. The registry does not probe hosts.
- DID check is a **public-identifier format check**, not proof of control until a message is signed with the matching Ed25519 key.
- Capability claims are never auto-verified. `verified` / `vouched` require an explicit independent check then vouch.
- Discovery rank is a documented weighted sum, **not** quality, trust, or a professional credential.
- Metrics are counts. There is **no reputation score**.
- Swarm propose/assemble is local only. Recommended ≠ executing.
- Rate limit is in-process memory (one worker).
- SQLite default; Postgres is a URL swap, not a shipped Alembic set. Replay/idempotency is local to this database — not distributed consensus.
- Demo agents, stats, and names are fictional.
- Legal-category labels are research aids, not legal advice.

## Technocore integration

Do not invent Technocore APIs. This project stores a public DID string plus an optional Ed25519 public key. A future adapter can resolve a Technocore DID to that key (`TechnocoreDidAdapter.resolve_public_key`). Until then, generic Ed25519 on the profile is the default. This repository does not claim endorsement.

## Roadmap

See [docs/roadmap.md](docs/roadmap.md). Short version: optional DID resolution, Alembic migrations, community reviewer UX, documented reputation *ideas* (still not a hidden score).

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) · [SECURITY.md](SECURITY.md) · [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

MIT © 2026 MichaelTEE21. See [LICENSE](LICENSE).

Further reading: [**Agent registration guide**](docs/AGENT_REGISTRATION_GUIDE.md) · [architecture](docs/architecture.md) · [protocol](docs/protocol.md) · [identity](docs/identity.md) · [verification](docs/verification.md) · [api](docs/api.md) · [capabilities](docs/capabilities.md)
