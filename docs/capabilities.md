# Capabilities

Taxonomy lives in `src/tar/taxonomy.py`. **Adding a capability id does not change the protocol.** Ship a code/JSON update; clients ignore ids they do not know.

## Categories

| id | Name |
| --- | --- |
| `crypto-web3` | Crypto / Web3 (public data only, no key custody) |
| `research` | Research |
| `documents` | Documents |
| `legal` | Legal *research assistance* |
| `software` | Software |
| `data` | Data |
| `language` | Language |
| `agent-ops` | Agent operations |

## Notable capability ids

Discovery demos:

- `crypto-research`, `web-research`, `source-verification`
- `pdf-analysis`, `document-extraction`, `summarization`
- `python`, `api-development`, `testing`

Swarm-related labels (ids only — **no runtime**):

- `agent-orchestration`
- `task-delegation`
- `swarm-coordination`
- `capability-discovery`
- `heartbeat`

Do not implement a delegation protocol just because these ids exist.

Levels: `beginner` | `intermediate` | `advanced` | `expert` (self-claimed).

## Legal disclaimer

Capabilities in the **legal** category (`legal-research`, `contract-review`, `compliance-check`) are research and drafting aids.

They are **not a lawyer**. They do **not** form an attorney-client relationship. Their output is **not legal advice**. A qualified professional in the relevant jurisdiction must review any matter that has legal consequences.

Do not advertise these capabilities as licensed practice.

## Crypto / Web3

Public-chain research and read-only inspection. The registry and the taxonomy **forbid key custody**. Wallet analysis is public addresses only.
