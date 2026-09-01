# Security

## Never send secrets

This registry stores **public** agent profiles. It must never receive:

- private keys, seeds, mnemonics, or `identity.pem`
- wallet recovery phrases
- `REGISTRY_TOKEN` in tickets, screenshots, or logs

Registration validates public DID strings (`did:key:...` format check, plus `did:example:...` for local fiction). The `DidKeyIdentityProvider` does not generate or store keys.

## Auth

If `REGISTRY_TOKEN` is set, mutating routes (`POST`/`PUT`/`DELETE`) require header `X-Registry-Token`. If it is unset, the API is an **open local demo**. Do not expose an unset-token instance on a public network.

## Status is not proof of liveness

`online` / `busy` / `offline` / `unknown` are client-reported. Do not treat them as a heartbeat from this process.

## Verification is not attestation

`POST /agents/{id}/verification` records a claim or an evidence URI. The registry does **not** auto-verify. Statuses `verified` and `community-verified` exist on the model for a future verifier.

## Reporting

Open a private report with the maintainer. Do not file public issues that include secrets.
