# Identity

The registry stores a **public DID string** and an optional **Ed25519 public key**. It never generates, imports, logs, or prints private key material.

## IdentityProvider

`tar.identity.IdentityProvider` validates a public DID string.

### DidKeyIdentityProvider

Accepts only `did:key:z` + base58btc encoding of multicodec **Ed25519-pub** (`0xed01`) + 32-byte public key. Charset check plus multibase/multicodec decode. Rejects PEM headers, the word `private`, seeds, and anything that is not a public identifier.

On registration (and when the DID changes on `PUT`), the registry **derives** `Agent.public_key` as **lowercase hex of the raw 32-byte Ed25519 public key**. A manually supplied `public_key` that does not match the DID is rejected (HTTP 400 / validation error).

### ExampleDidIdentityProvider

Accepts `did:example:...` for **FICTIONAL** local tests (`did:example:test-research`, and so on). Not a real network method.

`CompositeIdentityProvider` is the default.

## Signing (generic Ed25519)

Profile field `public_key` is **lowercase hex-encoded 32-byte Ed25519** (not multibase). Prefer derivation from `did:key`. Messages are signed over canonical JSON and verified with the registered public key (or derived did:key material). Invalid signatures are rejected. Presence of a signature is not proof; claims ≠ verified ≠ vouched.

### Technocore DID adapter

`tar.crypto.TechnocoreDidAdapter.resolve_public_key(did)` is the hook for a future Technocore resolver. The default returns `None`, so the profile public key is used. This project does not invent Technocore APIs and does not claim endorsement.

## What this is not

- Not a DID resolver (until an adapter is provided)
- Not a wallet
- Not proof of control until a signature verifies

## Distinguish

**Identity check ≠ signature valid ≠ agent verification status ≠ task complete ≠ result is true.**

A public DID format check is not proof of control. A valid Ed25519 signature is not a correct answer. Agent verification status is profile credence, not task completion.
