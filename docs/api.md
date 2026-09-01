# API

Base URL for local demo: `http://127.0.0.1:8080`

Interactive docs: `GET /docs` (FastAPI). Machine schema: `GET /openapi.json`.

## Auth

If `REGISTRY_TOKEN` is **unset**, mutating routes are open (local demo).

If `REGISTRY_TOKEN` is **set**, `POST`/`PUT`/`PATCH`/`DELETE` require:

```
X-Registry-Token: <token>
```

Reads stay open. 401 JSON:

```json
{"error": {"code": "unauthorized", "message": "..."}}
```

## Limits

- Max body: `MAX_REQUEST_BYTES` (default 65536) → 413
- Rate: `RATE_LIMIT_PER_MINUTE` (default 120 / IP / process) → 429

## Errors

Consistent envelope:

```json
{"error": {"code": "not_found", "message": "agent not found: x"}}
```

| HTTP | When |
| --- | --- |
| 201 | Created |
| 204 | Deleted |
| 400 | Bad filter / unknown member |
| 401 | Missing/wrong token |
| 404 | Missing resource |
| 409 | Duplicate id or DID |
| 413 | Body too large |
| 422 | Validation (including secret-looking fields) |
| 429 | Rate limit |

## Agents

- `POST /agents` body: agent profile
- `GET /agents?capability=&category=&status=`
- `GET /agents/{id}`
- `PUT /agents/{id}`
- `DELETE /agents/{id}`

`status` is client-reported: `online|busy|offline|unknown`.

## Capabilities

- `GET /capabilities`
- `GET /capabilities/{id}`
- `GET /capabilities?category=legal` includes the legal disclaimer field

## Verification

- `GET /agents/{id}/verification`
- `POST /agents/{id}/verification` `{kind, summary, evidence_uri?}` — records only

## Swarms

- `POST /swarms`
- `GET /swarms`
- `GET /swarms/{id}`
- `POST /swarms/{id}/members` `{agent_id}`
- `GET /swarms/assemble?capability=crypto-research` — proposed, not persisted; members are `online` or `unknown` only

Assemble does not invent liveness.
