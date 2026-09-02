# Agent-to-Agent Communication MVP Report

**Date:** 2026-09-02 (Africa/Johannesburg)  
**Tree:** `/workspace/technocore-prod`  
**Scope:** Extend existing Task / Message / workflow / `a2a.py` — **no rewrite from scratch**. **No deploy. No git push.**

**Disclaimer:** This is a **registry-mediated** A2A MVP. It is **not** an official FLOP protocol implementation. Structure is suitable for later FLOP adaptation when that spec lands. Public DID / public-key material only — **never** private keys. **No outbound HTTP** to agent endpoints in this MVP.

---

## Summary

| Area | Change |
|------|--------|
| Models | `Task.accepted_at`, `Task.completed_at` (nullable DateTime) |
| Workflow | Set timestamps on accept / submit_result |
| Protocol | `task.submit` / `SUBMIT` → `RESULT`; `FLOP_ADAPTATION` + `ProtocolAdapter` stub |
| API | `GET /tasks/{id}/history` (+ `/events` alias); `POST /tasks/{id}/submit` (= `/result`); `target_agent_id` synonym |
| UI | `/ui/communicate` + nav link; Discover “Request task” |
| Tests | `tests/test_a2a_mvp.py` (8) — **77 total** (69 prior + 8) |
| Demo | `scripts/demo_a2a_mvp.py` |

Identity productionize (69 tests) preserved. SQLAlchemy remains portable for Neon (ADD COLUMN uses portable `TIMESTAMP`, not SQLite-only SQL).

---

## Files changed / added

| Path | Change |
|------|--------|
| `src/tar/models.py` | `accepted_at`, `completed_at` on `Task` |
| `src/tar/db.py` | `_add_missing_columns` for `tasks.accepted_at` / `completed_at` |
| `src/tar/workflow.py` | Set timestamps in `accept_task` / `submit_result` |
| `src/tar/a2a.py` | SUBMIT aliases, `FLOP_ADAPTATION`, `ProtocolAdapter` stub |
| `src/tar/schemas.py` | `TaskCreate.target_agent_id`, `TaskOut` timestamps + alias, `TaskEventOut` / `TaskHistoryOut` |
| `src/tar/serialize.py` | Expose new TaskOut fields |
| `src/tar/api.py` | `/submit`, `/history`, `/events` |
| `src/tar/main.py` | `/ui/communicate` GET+POST |
| `src/tar/templates/communicate.html` | **New** communication UI |
| `src/tar/templates/base.html` | Nav link Communicate |
| `src/tar/templates/discover.html` | “Request task” → communicate |
| `tests/test_a2a_mvp.py` | **New** MVP coverage |
| `scripts/demo_a2a_mvp.py` | **New** local demo |
| `docs/A2A_MVP_REPORT.md` | This report |

### Unchanged (preserved)

- Identity / crypto / productionize paths
- Existing task routes (`POST /tasks`, `/accept`, `/reject`, `/result`, GET list/detail, messages)
- `api/index.py`, `vercel.json`, Postgres driver setup
- No private keys; no remote agent HTTP delivery

---

## Models

### `Task` (extended)

| Column | Type | Notes |
|--------|------|-------|
| `requester_id` | FK agents | Requester |
| `assignee_id` | FK agents (nullable) | Target / worker — API also exposes `target_agent_id` |
| `requested_capability` | str | Taxonomy id |
| `status` | str | State machine (below) |
| `result_json` | text | Completed payload |
| **`accepted_at`** | DateTime TZ, nullable | Set on accept |
| **`completed_at`** | DateTime TZ, nullable | Set on submit/result |
| `created_at` / `updated_at` | DateTime TZ | Existing |

Migration: portable `ALTER TABLE tasks ADD COLUMN … TIMESTAMP` via `_add_missing_columns` (SQLite + Postgres/Neon).

### Existing (kept)

- `Message` — REQUEST / ACCEPT / REJECT / PROGRESS / RESULT / VERIFY  
- `TaskEvent` — append-only workflow events  

---

## State machine

```
requested → accepted | rejected
accepted  → in_progress | rejected | failed
in_progress → completed | failed
completed → verified | disputed
…
```

MVP directed flow proof:

1. **REQUEST** — `POST /tasks` with assignee → status `requested` + REQUEST message  
2. **ACCEPT** — `POST /tasks/{id}/accept` → `accepted` + `accepted_at`  
3. **SUBMIT/RESULT** — `POST /tasks/{id}/submit` or `/result` → `completed` + `completed_at` + result  
4. Invalid transitions → **409**; wrong party → **403**; missing agent → **404**; capability mismatch → **400**

---

## Endpoints

| Method | Path | Notes |
|--------|------|-------|
| POST | `/tasks` | Create; `assignee` or `target_agent_id` |
| GET | `/tasks`, `/tasks/{id}` | List / detail (`accepted_at`, `completed_at`, `target_agent_id`) |
| POST | `/tasks/{id}/accept` | Existing |
| POST | `/tasks/{id}/reject` | Existing |
| POST | `/tasks/{id}/result` | Existing RESULT |
| POST | `/tasks/{id}/submit` | **New** alias → same as `/result` |
| GET | `/tasks/{id}/history` | **New** events + messages |
| GET | `/tasks/{id}/events` | **New** alias of history |
| GET | `/discover?capability=` | Existing — used by UI + tests |
| GET/POST | `/ui/communicate` | **New** UI |

---

## UI

- **`/ui/communicate`**: select Agent A (requester) + Agent B (target), show B capabilities, create task, ACCEPT / REJECT / SUBMIT as B, show status / result / history.  
- Nav: **Communicate** in `base.html`.  
- Discover cards: **Request task** deep-links with assignee + capability.  
- Design: existing cards / filters / timeline classes — minimal CSS change.

---

## Protocol (`a2a.py`)

- `MESSAGE_TYPE_ALIASES["task.submit"] = "RESULT"` and `["SUBMIT"] = "RESULT"`.  
- `FLOP_ADAPTATION` dict + `ProtocolAdapter` stub — **explicitly not claiming FLOP**.  
- `A2ATransport` still raises (no remote delivery).  

---

## Tests

| Suite | Count |
|-------|------:|
| Prior (identity + registry) | 69 |
| New `test_a2a_mvp.py` | 8 |
| **Total** | **77** |

Coverage includes: discover → create A→B → accept → submit → A sees result; reject path; accept-completed / submit-rejected 409; nonexistent agent; wrong requester/target; history persistence; SUBMIT vs RESULT; UI + nav; protocol aliases / FLOP stub.

Demo agents:

- **A** `mananze-technocore-agent` with productionize `did:key` (public key derived).  
- **B** `a2a-tokenomics-worker` with `tokenomics-analysis` (`did:example`, fictional).  
- Description: *Analyse the tokenomics of Project X.*  
- Result placeholders: Token supply / Allocation / Vesting.

---

## Ruff

```bash
ruff check src tests scripts
# All checks passed!
```

---

## Exact local demo commands

```bash
cd /workspace/technocore-prod
pip install -e .
PYTHONPATH=src python -m pytest -q
# 77 passed

ruff check src tests scripts

PYTHONPATH=src python scripts/demo_a2a_mvp.py

# Optional live UI (local only):
# PYTHONPATH=src uvicorn tar.main:create_app --factory --reload
# open http://127.0.0.1:8000/ui/communicate
```

---

## FLOP future notes

- Do **not** claim FLOP compliance.  
- When FLOP lands, map via `ProtocolAdapter` / `FLOP_ADAPTATION["message_map"]`.  
- Keep registry-mediated semantics until a peer transport exists.  
- SUBMIT remains a product alias for RESULT regardless of FLOP naming.

---

## Blockers / non-goals (intentional)

| Item | Status |
|------|--------|
| Outbound HTTP to agent `endpoint` | **Out of scope** (MVP registry-only) |
| Private key storage / signing in UI | **Forbidden** — UI uses agents without required pubkey, or API signs elsewhere |
| Official FLOP wire format | **Stub only** |
| Deploy / git push | **Not done** (per brief) |
| SQLite-only SQL | **Avoided** — portable TIMESTAMP ADD COLUMN |

---

## Mapping reminder (kept)

| Concept | Implementation |
|---------|----------------|
| requester / target | `requester_id` / `assignee_id` (+ API `target_agent_id`) |
| Statuses | requested → accepted\|rejected → in_progress → completed (RESULT) |
| Messages | REQUEST, ACCEPT, REJECT, PROGRESS, RESULT, VERIFY (+ SUBMIT→RESULT) |
