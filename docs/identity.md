# Identity

The registry stores a **public DID string**. It never generates, imports, or logs key material.

## IdentityProvider

`tar.identity.IdentityProvider` is the abstraction:

```python
def validate_public_did(self, did: str) -> str: ...
```

### DidKeyIdentityProvider

Accepts only `did:key:z` + base58btc. Conservative length/charset check. Rejects PEM headers, the word `private`, seeds, and anything that is not a public identifier. **No key decode beyond format.**

### ExampleDidIdentityProvider

Accepts `did:example:...` for **FICTIONAL** local tests (`did:example:test-research`, and so on). Not a real network method.

`CompositeIdentityProvider` is the default.

## What this is not

- Not a DID resolver
- Not a signer
- Not a wallet
- Not proof that the registrant controls the DID (FUTURE: signed profile)

Share only `did:key:z6Mk...` (or a documented example DID). Keep `identity.pem` on the operator machine.
