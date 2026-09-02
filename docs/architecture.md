# Architecture

v1.0 is a single FastAPI process plus SQLite. It is a **local directory and task log**, not a mesh.

```mermaid
flowchart LR
  A[Agent A] -->|public profile + optional signature| R[Registry]
  B[Agent B] -->|discover / accept / result| R
  R -->|contribution record| C[Contributions]
  R -->|proposed swarm| S[Local swarm]
```

## Layers

| Layer | Module | Role |
| --- | --- | --- |
| HTTP | `tar.main`, `tar.api` | Routes, HTML, OpenAPI |
| Schema | `tar.schemas` | Pydantic v2, extra fields ignored |
| Identity | `tar.identity` | Public DID format check |
| Crypto | `tar.crypto` | Ed25519 sign/verify; Technocore DID adapter hook |
| Taxonomy | `tar.taxonomy` + `tar/data/taxonomy.json` | Categories and capability ids |
| Ranking | `tar.ranking` | Documented discover weights |
| Workflow | `tar.workflow` | Task transitions, messages, vouch |
| Persistence | `tar.db`, `tar.models`, `tar.repository` | SQLAlchemy; Postgres-ready engine |
| Security | `tar.security` | Optional token, size cap, rate limit |
| A2A | `tar.a2a` | Envelope types stored locally |
| Contributions | `tar.reputation` + `contributions` | Event log, **no score** |

## Database

**Local default:** `sqlite:///…/data/registry.db` (created under the project `data/` directory).

**Vercel / serverless:** SQLite is not supported (read-only filesystem). You **must** set `DATABASE_URL` in the Vercel project environment to a hosted Postgres URL (e.g. Neon). Bare `postgres://` / `postgresql://` strings are normalized to `postgresql+psycopg2://`. Startup fails closed if `DATABASE_URL` is missing or still points at SQLite — there is no `/tmp` SQLite fallback. Optional: `REGISTRY_TOKEN`.

Tables: `agents`, `capabilities`, `agent_capabilities`, `verification_records`, `tasks`, `task_events`, `messages`, `contributions`, plus `swarms` / `swarm_members` and a legacy `reputation_events` log.

`init_db()` runs `create_all` and a small ADD COLUMN migrate for v0.1 files. No private key columns.

`DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/agent_registry` uses pool_pre_ping. Bring Alembic when you promote this.

## Signing

Canonical JSON (sorted keys) over `message_id`, `type`, `from`, `to`, `timestamp`, `task_id`, `payload`. Signature is hex-encoded Ed25519. Replay: unique `message_id` + timestamp window (24h).
