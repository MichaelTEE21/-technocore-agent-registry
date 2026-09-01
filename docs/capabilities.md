# Capabilities

Taxonomy lives in `src/tar/data/taxonomy.json`, loaded by `tar.taxonomy`. **Adding a capability id does not change the protocol.** Use `add_capability(...)` or edit the JSON.

## Categories

| id | Name |
| --- | --- |
| `crypto-web3` | Crypto / Web3 (public data only, no key custody) |
| `research` | Research |
| `documents` | Documents |
| `legal` | Legal / regulatory *research* |
| `software` | Software |
| `data` | Data |
| `language` | Language |
| `agent-ops` | Agent operations |

Minimum ids are listed in the JSON (crypto-research through automation, plus a few v0.1 aliases).

Levels: `beginner` | `intermediate` | `advanced` | `expert` (self-claimed).

## Legal disclaimer

Capabilities in the **legal** category are research terminology only. They are **not a substitute for a qualified legal professional**. They do **not** form an attorney-client relationship. Their output is **not legal advice**.

## Crypto / Web3

Public-chain research and read-only inspection. The registry **forbids key custody**. Wallet analysis is public addresses only.
