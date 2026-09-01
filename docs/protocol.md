# Protocol

Evolvable JSON over HTTP. Unknown fields are ignored. There is no binary framing and no WebSocket in v0.1.

## Agent profile

| Field | Notes |
| --- | --- |
| `id` | Registry-local slug |
| `name` | Display name |
| `did` | Public DID only |
| `version` | Agent's own version string |
| `description` | Free text |
| `capabilities[]` | `{id, category, level}` |
| `protocols[]` | How to speak to the endpoint, e.g. `http` |
| `status` | `online` \| `busy` \| `offline` \| `unknown` — **client-reported** |
| `endpoint` | `http(s)` URL or null |
| `verification.status` | See verification.md |

Never include private keys. The server rejects names such as `privateKey`, `seed`, `mnemonic`.

## Status

The registry does not probe `endpoint`. `online` means "the owner last said so." Treat `unknown` as a valid assemble candidate; exclude `offline` and `busy` from assemble (busy is occupied, not missing).

Assemble includes `online` and `unknown` only.

## Swarm

A swarm is a named grouping:

```json
{
  "id": "demo-core",
  "name": "Demo Core Swarm",
  "description": "...",
  "member_agent_ids": ["test-research", "test-document", "test-developer"],
  "required_capabilities": ["crypto-research", "pdf-analysis", "python"]
}
```

`GET /swarms/assemble?capability=crypto-research` returns the same shape with `proposed: true`, `persisted: false`.

## FUTURE A2A

Types only, in `tar.a2a`:

`REQUEST` `ACCEPT` `REJECT` `PROGRESS` `RESULT` `VERIFY`

This registry will not grow a hidden message bus in a patch release. A future protocol doc would own delivery semantics.
