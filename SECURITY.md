# Security

## Disclosure

Report vulnerabilities privately to the maintainer. Do not file public issues that include secrets, private keys, seeds, or tokens. We aim to acknowledge reports within a reasonable time and to ship a fix before any coordinated disclosure.

This is a local reference implementation. Do not expose an instance with `REGISTRY_TOKEN` unset on a public network.

## Never send secrets

This registry stores **public** agent profiles. It must never receive:

- private keys, seeds, mnemonics, or `identity.pem`
- wallet recovery phrases
- `REGISTRY_TOKEN` in tickets, screenshots, or logs

Registration validates public DID strings (`did:key:...` format check, plus `did:example:...` for local fiction). The `DidKeyIdentityProvider` does not generate or store keys.

Demo Ed25519 private keys live only in gitignored `data/keys/` or process temp files. They are never printed.

## Signing

Generic Ed25519 over canonical JSON is the default. Invalid signatures are rejected. `tar.crypto.TechnocoreDidAdapter` is the hook for a future Technocore DID resolver; it returns `None` today so the profile `public_key` is used. Do not invent Technocore APIs here.

## Authz

- Mutating HTTP routes may require `X-Registry-Token` when `REGISTRY_TOKEN` is set.
- Task accept/progress/result must be performed by the assignee.
- Task verify/vouch must be an **independent** agent (not the assignee).
- Capability vouch requires a prior independently-checked record.

## Other controls

- Request size cap (`MAX_REQUEST_BYTES`)
- In-process rate limit (`RATE_LIMIT_PER_MINUTE`)
- Safe JSON error bodies (no stack traces)
- Pinned dependencies in `requirements.txt`
- No PII collection

## Status is not proof of liveness

`online` / `busy` / `offline` / `unknown` are client-reported.

## Verification is not attestation

Evidence URIs are pointers. The registry does **not** auto-verify capability claims.
