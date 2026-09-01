# Changelog

## Unreleased

- Public Agent Network UI (v2): landing, directory, DID connect, capability explorer, protocol, developers, contribution proof views. HTML/CSS only; v1 API and tar.a2a unchanged.

- Protocol contract `tar.a2a` **1.0**: JSON Schemas in `docs/protocol/`, language-agnostic `docs/protocol.md`.
- Task timeline on `/ui/tasks/{id}` with ordered events and signature `VALID` / `INVALID` / `UNSIGNED`.
- Lightweight Python client `tar_client.TarClient` (discover, task actions, `verify_message` via `tar.crypto`).
- Replay/idempotency documented: duplicate `message_id` / `task_id` → 409 (local SQLite, not consensus).
- `POST /messages/{id}/verify` (envelope crypto only; distinct from `/tasks/{id}/verify`).
- START.bat / START.ps1 banner **MANANZE — TECHNOCORE AGENT REGISTRY**; missing Python → "Please tell MANANZE."
- Paste a public DID: `GET /lookup`, `/ui/lookup`, and `python -m tar_cli lookup`.
- Downloadable public-profile proof snapshot (`tar.proof.profile.v1`) via `GET /proof` and `GET /agents/{id}/proof`. Records `profile_proof_generated` (not money). Private keys never included.

## 1.0.0 — 2026-09-01

Local workflow complete: register → discover → delegate → sign → vouch → contribute → swarm.

- Data-driven taxonomy (`src/tar/data/taxonomy.json`) with required Crypto/Web3, research, documents, legal/regulatory, software, data, language, and agent-ops ids. Safe add without a protocol bump.
- Agent profiles: public Ed25519 key, capability evidence status, schema-validated JSON.
- `GET /discover` with documented ranking (capability match, verification, availability, compatibility, evidence). No AI quality scores. Pagination and protocol filter on `GET /agents`.
- Tasks with strict states: requested, accepted, rejected, in_progress, completed, failed, verified, disputed.
- A2A messages REQUEST/ACCEPT/REJECT/PROGRESS/RESULT/VERIFY with replay protection and Ed25519 signatures. Private keys never stored or printed.
- Credence TASK → ACCEPT → SUBMIT → VOUCH. Independent re-run required before vouch. Capability claims never auto-verified.
- Contributions event log and per-agent metrics (counts, not a score).
- Swarm propose/assemble distinguishes recommended vs executing. Local only.
- Five fictional demo agents (crypto, legal research, document, developer, security).
- CLI: register, profile, capabilities, discover, task create/accept/result, verify, contributions, swarm.
- Web: agents, capabilities, profiles, verification/metrics, tasks, contributions, swarm, search/filter.
- GitHub Actions: ruff + pytest + demo_flow.
- Docs rewritten (README PowerShell and POSIX, api, architecture, protocol, security).

## 0.1.0 — 2026-09-01

First public MVP.

- Agent profile registry (register, get, list, update, delete)
- Capability taxonomy (in-process)
- Client-reported status; no liveness probing
- Verification records as claims/evidence/disputes — no auto-verify
- Reputation *events* table with no score calculation
- Swarm data model, assemble-by-capability, demo swarm of three fictional agents
- A2A envelope types only
- REST API, CLI, HTML demo, docs
