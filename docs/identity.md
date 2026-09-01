# Identity

The registry stores a **public DID string** and an optional **Ed25519 public key**. It never generates, imports, logs, or prints private key material.

## IdentityProvider

`tar.identity.IdentityProvider` validates a public DID string.

### DidKeyIdentityProvider

Accepts only `did:key:z` + base58btc. Conservative length/charset check. Rejects PEM headers, the word `private`, seeds, and anything that is not a public identifier.

### ExampleDidIdentityProvider

Accepts `did:example:...` for **FICTIONAL** local tests (`did:example:test-research`, and so on). Not a real network method.

`CompositeIdentityProvider` is the default.

## Signing (generic Ed25519)

Profile field `public_key` is hex-encoded 32-byte Ed25519. Messages are signed over canonical JSON. Invalid signatures are rejected.

### Technocore DID adapter

`tar.crypto.TechnocoreDidAdapter.resolve_public_key(did)` is the hook for a future Technocore resolver. The default returns `None`, so the profile public key is used. This project does not invent Technocore APIs and does not claim endorsement.

## What this is not

- Not a DID resolver (until an adapter is provided)
- Not a wallet
- Not proof of control until a signature verifies
