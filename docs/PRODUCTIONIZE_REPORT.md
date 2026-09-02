# Technocore Agent Registry — Productionize Report

**Date:** 2026-09-02 (Africa/Johannesburg)  
**Tree:** `/workspace/technocore-prod` (synced from GitHub `dcb3a45`)  
**Scope:** Extend existing architecture. **No deploy. No git push.**

**Disclaimer:** This is an independent open-source reference registry. It is **not** an official Technocore network component and does **not** invent or assert official Technocore membership. Public DID / public-key material only — never private keys, PEM, seeds, or passphrases.

---

## Summary

Productionization focused on:

1. Deriving and storing Ed25519 `public_key` from valid `did:key` (multibase `z` + multicodec `0xed01`).
2. Correct **fictional/demo** defaults (non-demo no longer defaults to fictional).
3. Safer **PUT /agents/{id}** metadata whitelist (DID recompute, endpoint URL shape only, no credential injection).
4. Preserving TASK → ACCEPT → SUBMIT → VOUCH and CLAIMED ≠ VERIFIED ≠ VOUCHED.
5. UI profile clarity (public key, endpoint, DID state, demo label).
6. Comprehensive tests + ruff clean. Preserved `api/index.py`, `vercel.json`, `DATABASE_URL` / Postgres driver.

---

## Files changed

| Path | Change |
|------|--------|
| `src/tar/crypto.py` | Pure-Python base58btc decode; `ed25519_public_key_from_did_key`; `resolve_registration_public_key`; verify path can fall back to did:key |
| `src/tar/identity.py` | did:key validation now decodes multicodec Ed25519-pub; `extract_public_key_hex`; `is_demo_did` |
| `src/tar/schemas.py` | `AgentCreate.fictional` default **False**; derive/match public_key; `AgentUpdate` whitelist + `did`/`fictional`/endpoint validators; clearer verification note |
| `src/tar/models.py` | ORM `Agent.fictional` insert default `"false"` (does **not** rewrite existing rows) |
| `src/tar/api.py` | Register derives public_key + demo flag; PUT uses `exclude_unset` whitelist, DID change recomputes key |
| `src/tar/main.py` | UI register form no longer forces `fictional=True` when unchecked |
| `src/tar/templates/agent.html` | Shows public key, endpoint, DID verification state, demo vs non-demo labels |
| `docs/identity.md` | Document hex format + did:key derivation |
| `tests/test_productionize.py` | **New** coverage (did:key, mismatch, create, demo, PUT, proofs, SQLite, UI) |
| `scripts/manual_fix_agent_pubkey.py` | **New** optional one-shot manual helper (dry-run by default path) |
| `docs/PRODUCTIONIZE_REPORT.md` | This report |

### Unchanged (preserved)

- `api/index.py` — Vercel Python entry
- `vercel.json` — routes/builds
- `requirements.txt` / `pyproject.toml` — still `cryptography` + `psycopg2-binary`; **no** PyNaCl / multiformats (pure-Python base58)
- Proof / workflow TASK→ACCEPT→SUBMIT→VOUCH logic (clarified in responses/UI only)

---

## Model / API / security changes

### `Agent.public_key` format

- **Stored as:** lowercase **hex** of the raw **32-byte Ed25519** public key (not multibase).
- For `did:key:z…` with multicodec **Ed25519-pub (`0xed01`)**, the key is **derived from the DID** on create and whenever DID changes on PUT.
- Manually supplied `public_key` that does not match the DID is **rejected**.
- Key-material pastes (PEM, `private`, seed, etc.) remain rejected.

### Fictional / demo

| Case | `fictional` |
|------|-------------|
| New non-demo agent (`did:key:…`, flag omitted) | **false** |
| `did:example:…` | always **true** |
| Explicit `"fictional": true` | true |
| Demo seed (`scripts/seed_demo.py`) | still seeds `"true"` |
| Existing DB rows | **not** mass-converted |

API `AgentOut.fictional` remains a boolean; UI shows **DEMO / FICTIONAL** vs **Non-demo registration**.

### PUT `/agents/{agent_id}` whitelist

Allowed when set: `name`, `did`, `version`, `description`, `capabilities`, `protocols`, `status`, `endpoint`, `public_key`, `fictional`.

- Extra unknown fields ignored (Pydantic `extra=ignore`).
- Secret field names rejected at validation boundary.
- `endpoint`: http(s) URL format only, or `""`/`null` to clear — **never fetched**.
- DID change → unique check + recompute `public_key`; `did:example:` cannot be forced non-fictional.

### Verification

- Unchanged machine: claim/evidence stay **claimed**; `independently-checked` then **vouch** → agent `vouched`, capability `community-verified`.
- Message signatures verified against registered (or did:key-derived) public key.
- Responses/UI emphasize **CLAIMED ≠ VERIFIED ≠ VOUCHED**.

### Known public DID (docs only — no private key)

```
did:key:z6Mkrv5ZL3VsapUdVKirgFiJVdw7y5w8Bq3zDvmfNMDSAAep
→ public_key hex:
b92b11242fc30b0a9d1f445c4a17bab043e0842b6defa74fe812fc75d8b12fcd
```

---

## Tests

```text
pytest  →  69 passed
ruff    →  All checks passed
```

New file `tests/test_productionize.py` covers:

- valid did:key pubkey extraction  
- malformed / unsupported DID  
- pubkey mismatch reject  
- create agent (non-demo default + derived key)  
- demo/fictional create  
- PUT metadata whitelist + secret reject  
- invalid / clear endpoint  
- DID change recomputes public_key  
- proof/signature verify + capability claim → check → vouch  
- key-material reject  
- SQLite roundtrip (portable SQLAlchemy)  
- UI profile shows pubkey / endpoint / non-demo label  

---

## Migrations required

**No destructive migration.** Column `agents.public_key` and `agents.fictional` already exist.

- New inserts use `fictional` default `"false"` when omitted at the ORM layer; application still sets the flag explicitly.
- Existing Neon/SQLite rows are **left as-is** (no silent mass-convert).
- Optional: after deploy of this code, **manually** update specific agents via PUT (see below).

Lightweight `db._add_missing_columns` remains SQLite-oriented ADD COLUMN helpers; models stay portable for Neon/Postgres.

---

## Manual actions (do not auto-mutate production Neon)

### Update `mananze-technocore-agent` (public key + fictional=false)

Prefer authenticated API PUT against the environment you intend (staging first):

```bash
curl -X PUT "$BASE/agents/mananze-technocore-agent" \
  -H "Content-Type: application/json" \
  -H "X-Registry-Token: $REGISTRY_TOKEN" \
  -d '{
    "did": "did:key:z6Mkrv5ZL3VsapUdVKirgFiJVdw7y5w8Bq3zDvmfNMDSAAep",
    "fictional": false
  }'
```

This derives and stores:

`public_key = b92b11242fc30b0a9d1f445c4a17bab043e0842b6defa74fe812fc75d8b12fcd`

Optional offline helper (local/staging only; refuses write without confirmation):

```bash
DATABASE_URL=sqlite:///./data/registry.db \
  python scripts/manual_fix_agent_pubkey.py \
    --agent-id mananze-technocore-agent \
    --did did:key:z6Mkrv5ZL3VsapUdVKirgFiJVdw7y5w8Bq3zDvmfNMDSAAep \
    --fictional false \
    --dry-run
```

**Do not** point this helper at production Neon without an explicit, reviewed ops step.

### Deploy notes (out of scope here)

- Deploy is intentionally **not** performed by this workstream.
- Keep `DATABASE_URL` (Neon) and `REGISTRY_TOKEN` in the host env; never commit secrets.

---

## Security checklist

- [x] No private keys / PEM / seeds / passphrases stored or requested  
- [x] Only public DID / public-key material  
- [x] No invented official Technocore membership  
- [x] Independent / open-source disclaimer retained in app description, proofs, and this report  
