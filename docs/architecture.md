# Architecture

v0.1 is a single FastAPI process plus SQLite. It is a **directory**, not a mesh.

```mermaid
flowchart TB
  subgraph clients [Clients]
    UI[HTML demo]
    CLI[tar_cli]
    HTTP[Any HTTP client]
  end
  subgraph app [technocore-agent-registry]
    API[REST API]
    TAX[Taxonomy JSON-in-code]
    ID[IdentityProvider]
    DB[(SQLite / Postgres-ready)]
  end
  UI --> API
  CLI --> API
  HTTP --> API
  API --> TAX
  API --> ID
  API --> DB
```

## Layers

| Layer | Module | Role |
| --- | --- | --- |
| HTTP | `tar.main`, `tar.api` | Routes, HTML, OpenAPI |
| Schema | `tar.schemas` | Pydantic v2, extra fields ignored |
| Identity | `tar.identity` | Public DID format check only |
| Taxonomy | `tar.taxonomy` | Categories and capability ids |
| Persistence | `tar.db`, `tar.models` | SQLAlchemy session factory |
| Security | `tar.security` | Optional token, size cap, rate limit |
| A2A | `tar.a2a` | Envelope types — **not transported** |
| Reputation | `tar.reputation` + `reputation_events` | Event log, **no score** |

## Swarm

A swarm is `{id, name, description, member_agent_ids[], required_capabilities[]}`.

The registry stores named swarms and can **propose** one via `GET /swarms/assemble`. Proposal uses advertised capabilities and client-reported `online`/`unknown` status. It does not ping endpoints.

Messaging between members is **FUTURE**.

## Database

Default: `sqlite:///./data/registry.db` with `check_same_thread=False`.

`make_engine()` is Postgres-ready: non-SQLite URLs get `pool_pre_ping`, `pool_size`, `max_overflow`. Example:

```
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/agent_registry
```

v0.1 uses `create_all`. Bring your own migrations if you promote this.

## Process

```
uvicorn tar.main:app --app-dir src
```

HTML templates and static art (logo, swarm, sales-hero, og) ship inside the `tar` package.
