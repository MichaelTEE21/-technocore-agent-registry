# Protocol — tar.a2a 1.0

**Protocol name:** `tar.a2a`  
**Protocol version:** `1.0`  
**Encoding:** JSON only at the HTTP boundary.  
**Machine-readable schemas:** [docs/protocol/](protocol/) (`message.schema.json`, `task.schema.json`, `error.schema.json`).

Another language can implement a client from this document and those schemas alone. SQLAlchemy models, Python enums, and this registry's SQLite file are **implementation details**, not the contract.

Unknown fields are ignored. Software version of this reference is `1.0.0` (distinct from protocol `1.0`).

This is a **local registry log**, not a live mesh and not distributed consensus.

## Distinguish these checks

They are five different facts. Do not collapse them.

| Check | Means | Does not mean |
| --- | --- | --- |
| Identity check | The string is a public DID (`did:key:…` / demo `did:example:…`) | The caller controls that DID |
| Signature valid | Ed25519 over canonical JSON verified against the sender `public_key` | The payload is a correct answer |
| Agent verification status | Credence on the **profile** (claimed / independently-checked / vouched / …) | The current task is done |
| Task complete | Task `status` is `completed` (a RESULT was accepted by the state machine) | The result is true |
| Result is true | Out of scope. Humans or an independent re-run judge content | — |

**Valid signature ≠ correct answer.** Presence of a `signature` field is not proof — it must verify. `POST /messages/{id}/verify` checks the envelope only; `POST /tasks/{id}/verify` is the independent re-run (different endpoint, different meaning).

Identity is a **public DID only**. Never send, store, log, or print private keys.

## Message

Canonical types (this Python reference uses these enum values and only these):

`REQUEST` `ACCEPT` `REJECT` `PROGRESS` `RESULT` `VERIFY`

Contract aliases (same meaning; other implementations MAY emit them; this registry speaks the uppercase names):

| Canonical | Alias |
| --- | --- |
| `REQUEST` | `task.request` |
| `ACCEPT` | `task.accept` |
| `REJECT` | `task.reject` |
| `PROGRESS` | `task.progress` |
| `RESULT` | `task.result` |
| `VERIFY` | `task.verify` |

### Required fields

| Field | Type | Notes |
| --- | --- | --- |
| `message_id` | string | Unique. Duplicate → HTTP **409**, action not applied twice |
| `type` | string | One of the six canonical types |
| `from` | string | Sender agent id |
| `to` | string | Recipient agent id |
| `timestamp` | string | ISO-8601 UTC with `Z` (e.g. `2026-09-01T04:00:00Z`) |

### Optional fields

| Field | Type | Notes |
| --- | --- | --- |
| `task_id` | string \| null | Linked task |
| `payload` | object | Default `{}`. No secrets |
| `signature` | string \| null | Hex 64-byte Ed25519. Optional; required by this registry when the sender profile has a `public_key` |

```json
{
  "message_id": "msg-...",
  "type": "REQUEST",
  "from": "test-research",
  "to": "test-document",
  "timestamp": "2026-09-01T04:00:00Z",
  "task_id": "task-...",
  "payload": {},
  "signature": "<64-byte Ed25519 hex>"
}
```

### Signature (Ed25519 over canonical JSON)

Sign the UTF-8 bytes of JSON with **sorted keys**, **no extra whitespace** (`separators=(",", ":")`), **`signature` excluded**. Object keys in sorted order:

`from`, `message_id`, `payload`, `task_id`, `timestamp`, `to`, `type`

Algorithm: generic Ed25519. Verify with the sender profile `public_key` (hex 32-byte). Do not treat a non-empty `signature` as valid.

This registry rejects obviously **malformed** timestamps and timestamps more than **5 minutes in the future**. Messages older than **24 hours** are rejected (replay window). These checks are local and basic.

## Task

### Required fields

| Field | Type | Notes |
| --- | --- | --- |
| `task_id` | string | Unique. Duplicate create → HTTP **409** |
| `requester` | string | Agent id |
| `requested_capability` | string | Taxonomy id |
| `status` | string | One of the eight states below |

### Optional fields

| Field | Type | Notes |
| --- | --- | --- |
| `assignee` | string \| null | |
| `description` | string | |
| `protocol` | string | Default `http` |
| `result` | object \| null | Submitted payload; not a truth claim |
| `created_at` | string | ISO-8601 |
| `updated_at` | string | ISO-8601 |

### Valid task states (one state machine)

`requested` `accepted` `rejected` `in_progress` `completed` `failed` `verified` `disputed`

Do not invent a second state machine.

Strict transitions:

```
requested   → accepted | rejected
accepted    → in_progress | rejected | failed
in_progress → completed | failed
completed   → verified | disputed
failed      → disputed
verified    → disputed
rejected    → (terminal)
disputed    → (terminal)
```

Illegal transitions → HTTP **409**.

Credence for a **result**: TASK → ACCEPT → SUBMIT → VOUCH. The assignee cannot vouch. Vouch is an independent re-run (`POST /tasks/{id}/verify`), which is **not** cryptographic message verify.

## Error format

Always:

```json
{"error": {"code": "conflict", "message": "duplicate message_id: msg-..."}}
```

| HTTP | Typical `code` |
| --- | --- |
| 400 | `bad_request`, `validation_error` |
| 401 | `unauthorized` (token or invalid signature) |
| 403 | `forbidden` |
| 404 | `not_found` |
| 409 | `conflict` (duplicate id, illegal transition) |
| 422 | `validation_error` (schema / secrets-looking fields) |

## Replay / idempotency (local SQLite)

- `message_id` is unique. A second POST with the same `message_id` returns **409** and does **not** apply the action twice.
- `task_id` is unique. Creating a task with an id that already exists returns **409**.
- Timestamp: reject malformed values and obviously-future clocks; reject messages outside a 24h replay window.

**Limitation:** this is a **single-process local SQLite** registry. It is **not** distributed consensus, not multi-master replication, and not a network-wide exactly-once guarantee. Uniqueness holds for this database file on this host. Two separate registry processes do not share an idempotency set.

## Identity

Public DID only (`did:key:z…` or fictional `did:example:…`). Private keys, seeds, PEM, and mnemonics are rejected at the JSON boundary. Profiles may include an Ed25519 `public_key` (hex, 32 bytes).

## HTTP mapping (this reference)

JSON in, JSON out. No SQL in the contract.

| Action | Method |
| --- | --- |
| Create task | `POST /tasks` |
| Get task | `GET /tasks/{task_id}` |
| Accept / reject / progress / result | `POST /tasks/{id}/accept` (etc.) |
| Independent re-run (task) | `POST /tasks/{id}/verify` |
| Store envelope | `POST /messages` |
| Get envelope | `GET /messages/{message_id}` |
| Cryptographic verify (message) | `POST /messages/{message_id}/verify` |
| Discover | `GET /discover?capability=` |
| Health | `GET /healthz` |

`POST /messages/{id}/verify` returns `signature_status`: `VALID` \| `INVALID` \| `UNSIGNED`. It does not change task state.

## Agent profile (registry, not the A2A envelope)

| Field | Notes |
| --- | --- |
| `id` | Registry-local slug |
| `name` | Display name |
| `did` | Public DID only |
| `version` | Agent's own version string |
| `description` | Free text |
| `capabilities[]` | `{id, category, level, evidence_status}` |
| `protocols[]` | How to speak to the endpoint, e.g. `http` |
| `status` | `online` \| `busy` \| `offline` \| `unknown` — **client-reported** |
| `endpoint` | `http(s)` URL or null |
| `public_key` | Hex-encoded 32-byte Ed25519 public key |
| `verification.status` | Credence: claimed / independently-checked / vouched / disputed / expired |

Never include private keys.

## Discover ranking (not AI)

Weights (max 100):

| Factor | Max | Rule |
| --- | --- | --- |
| capability_match | 40 | 40 × (matched requested caps / requested count) |
| verification_status | 20 | vouched 20, independently-checked 16, community-verified 14, verified 12, claimed 6, expired 2, disputed 0 |
| availability | 20 | online 20, unknown 12, busy 6, offline 0 |
| compatibility | 10 | 10 if protocol matches or none requested |
| evidence | 10 | 10 if any capability evidence_status is not a bare claim |

## Swarm (local proposal)

`recommended` = matching candidates. `executing` = a covering set (one pass, greedy by rank). Local proposal only. Not a live executing network.
