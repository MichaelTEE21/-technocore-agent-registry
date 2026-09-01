# Roadmap

## v0.1 (this tree)

- Profile CRUD, taxonomy, HTML demo, CLI
- Named swarms + assemble-by-capability
- Claim/evidence verification records
- Reputation **events** without a score
- A2A **types** without a network

## Next (still discovery)

- Signed profile documents (public key in DID, signature over canonical JSON)
- Optional token still, plus per-agent bearer for self-update
- Postgres alembic migrations
- Pagination and ETags
- Community-verified workflow (human/agent reviewers, still no silent auto-verify)

## Later (labeled FUTURE in the code)

- Reputation score derived from events (documented weights, not a black box)
- A2A messaging plane: REQUEST / ACCEPT / REJECT / PROGRESS / RESULT / VERIFY
- Task delegation / orchestration **runtime** (taxonomy ids already exist)
- Federation between registries

Nothing in FUTURE should be mistaken for a hidden v0.1 feature.
