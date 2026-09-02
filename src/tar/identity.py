"""Identity providers. Public DIDs only — never private keys, seeds, or PEM material."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from tar.crypto import SignatureError, ed25519_public_key_from_did_key, public_key_hex

# W3C did:key uses multibase base58btc (prefix `z`). Alphabet excludes 0 O I l.
_DID_KEY_RE = re.compile(r"^did:key:z[1-9A-HJ-NP-Za-km-z]{32,128}$")
_DID_EXAMPLE_RE = re.compile(r"^did:example:[A-Za-z0-9._:-]{1,200}$")

# Substrings that indicate key material rather than a public identifier.
_FORBIDDEN_FRAGMENTS = (
    "private",
    "secret",
    "seed",
    "mnemonic",
    "begin ",
    "-----",
    "identity.pem",
    "privkey",
)


def looks_like_key_material(value: str) -> bool:
    """True when a paste looks like a private key, seed, PEM, or similar secret."""
    if not isinstance(value, str):
        return False
    lower = value.lower()
    return any(frag in lower for frag in _FORBIDDEN_FRAGMENTS)


def _reject_key_material(value: str) -> None:
    if looks_like_key_material(value):
        raise IdentityError("DID must be a public identifier; key material is rejected")


class IdentityError(ValueError):
    """Raised when a DID is not a public identifier this provider accepts."""


class IdentityProvider(ABC):
    """Validate a public DID string. Implementations must never accept key material."""

    method: str

    @abstractmethod
    def validate_public_did(self, did: str) -> str:
        """Return the normalized DID or raise IdentityError."""


class DidKeyIdentityProvider(IdentityProvider):
    """Accepts public ``did:key:...`` with Ed25519-pub multicodec (0xed01).

    Validates charset, multibase decode, and multicodec. Never generates keys,
    never stores private keys, and never accepts PEM/seed pastes.
    """

    method = "key"

    def validate_public_did(self, did: str) -> str:
        if not isinstance(did, str):
            raise IdentityError("DID must be a string")
        value = did.strip()
        lower = value.lower()
        for frag in _FORBIDDEN_FRAGMENTS:
            if frag in lower:
                raise IdentityError("DID must be a public identifier; key material is rejected")
        if not value.startswith("did:key:"):
            raise IdentityError("DidKeyIdentityProvider only accepts did:key public identifiers")
        if _DID_KEY_RE.fullmatch(value) is None:
            raise IdentityError("did:key failed public-identifier format check")
        try:
            ed25519_public_key_from_did_key(value)
        except SignatureError as exc:
            raise IdentityError(str(exc)) from exc
        return value

    def extract_public_key_hex(self, did: str) -> str:
        """Return lowercase hex of the Ed25519 public key embedded in did:key."""
        normalized = self.validate_public_did(did)
        return public_key_hex(ed25519_public_key_from_did_key(normalized))


class ExampleDidIdentityProvider(IdentityProvider):
    """Demo/test DID method `did:example:...`. Not a real network identifier."""

    method = "example"

    def validate_public_did(self, did: str) -> str:
        if not isinstance(did, str):
            raise IdentityError("DID must be a string")
        value = did.strip()
        lower = value.lower()
        for frag in _FORBIDDEN_FRAGMENTS:
            if frag in lower:
                raise IdentityError("DID must be a public identifier; key material is rejected")
        if _DID_EXAMPLE_RE.fullmatch(value) is None:
            raise IdentityError("did:example failed public-identifier format check")
        return value


class CompositeIdentityProvider(IdentityProvider):
    """Dispatch by DID method. Default: did:key + did:example (fictional tests)."""

    method = "composite"

    def __init__(self, providers: list[IdentityProvider] | None = None) -> None:
        self.providers = providers or [
            DidKeyIdentityProvider(),
            ExampleDidIdentityProvider(),
        ]

    def validate_public_did(self, did: str) -> str:
        if not isinstance(did, str):
            raise IdentityError("DID must be a string")
        value = did.strip()
        _reject_key_material(value)
        if not value or ":" not in value:
            raise IdentityError("DID must be a did:<method>:<id> public identifier")
        parts = value.split(":")
        if len(parts) < 3 or parts[0] != "did":
            raise IdentityError("DID must be a did:<method>:<id> public identifier")
        method = parts[1]
        last_error: IdentityError | None = None
        for provider in self.providers:
            if provider.method in {method, "composite"}:
                try:
                    return provider.validate_public_did(value)
                except IdentityError as exc:
                    last_error = exc
        if last_error:
            raise last_error
        raise IdentityError(f"Unsupported DID method: {method}")


def is_demo_did(did: str) -> bool:
    """True for fictional ``did:example:`` identifiers used in local demos/tests."""
    return isinstance(did, str) and did.strip().startswith("did:example:")


default_identity_provider = CompositeIdentityProvider()
