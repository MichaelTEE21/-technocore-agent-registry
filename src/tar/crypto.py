"""Ed25519 sign/verify and did:key public-key extraction.

Private keys never enter the registry database, logs, or printed output.
They live only in demo agent processes or gitignored temp files.

Agent.public_key format: lowercase hex encoding of the raw 32-byte Ed25519
public key (not multibase). When the agent DID is did:key with multicodec
Ed25519-pub (0xed01), the registry derives and stores this hex from the DID.

Default algorithm: generic Ed25519 over canonical JSON.
Adapter point: TechnocoreDidAdapter.resolve_public_key(did) — unset by default.
"""

from __future__ import annotations

import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

SIGNATURE_ALG = "ed25519"

# Multibase base58btc alphabet (Bitcoin / did:key). Excludes 0 O I l.
_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_INDEX = {c: i for i, c in enumerate(_B58_ALPHABET)}

# Multicodec prefix for Ed25519 public key (varint 0xed followed by 0x01).
_ED25519_MULTICODEC = b"\xed\x01"
_ED25519_PUB_LEN = 32


class SignatureError(ValueError):
    """Invalid key material or signature."""


def b58btc_decode(value: str) -> bytes:
    """Decode multibase base58btc (no leading 'z'). Pure Python — no extra deps."""
    if not value or not isinstance(value, str):
        raise SignatureError("invalid base58btc input")
    try:
        n = 0
        for ch in value:
            n = n * 58 + _B58_INDEX[ch]
    except KeyError as exc:
        raise SignatureError("invalid base58btc character") from exc
    pad = 0
    for ch in value:
        if ch == "1":
            pad += 1
        else:
            break
    if n == 0:
        raw = b""
    else:
        raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return b"\x00" * pad + raw


def ed25519_public_key_from_did_key(did: str) -> bytes:
    """Extract raw 32-byte Ed25519 public key from a did:key identifier.

    Expects ``did:key:z`` + base58btc(multicodec 0xed01 || 32-byte pubkey).
    Raises SignatureError on malformed or unsupported multicodec material.
    """
    if not isinstance(did, str):
        raise SignatureError("DID must be a string")
    value = did.strip()
    if not value.startswith("did:key:"):
        raise SignatureError("not a did:key identifier")
    method_id = value[len("did:key:") :]
    if not method_id.startswith("z") or len(method_id) < 34:
        raise SignatureError("did:key must use multibase base58btc (z prefix)")
    try:
        raw = b58btc_decode(method_id[1:])
    except SignatureError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise SignatureError("failed to decode did:key multibase") from exc
    if len(raw) < 2 + _ED25519_PUB_LEN:
        raise SignatureError("did:key multicodec payload too short")
    if not raw.startswith(_ED25519_MULTICODEC):
        raise SignatureError(
            "unsupported did:key multicodec; only Ed25519-pub (0xed01) is accepted"
        )
    pub = raw[2 : 2 + _ED25519_PUB_LEN]
    if len(pub) != _ED25519_PUB_LEN or len(raw) != 2 + _ED25519_PUB_LEN:
        raise SignatureError("did:key Ed25519 public key must be exactly 32 bytes")
    try:
        Ed25519PublicKey.from_public_bytes(pub)
    except Exception as exc:  # noqa: BLE001
        raise SignatureError("invalid Ed25519 public key in did:key") from exc
    return pub


def try_public_key_from_did(did: str) -> bytes | None:
    """Return Ed25519 raw pubkey for did:key, else None for did:example / unknown."""
    if not isinstance(did, str):
        return None
    value = did.strip()
    if not value.startswith("did:key:"):
        return None
    return ed25519_public_key_from_did_key(value)


def resolve_registration_public_key(
    did: str, supplied_hex: str | None
) -> str | None:
    """Derive public_key hex from did:key; reject mismatch with a supplied key.

    Format stored: lowercase hex of 32 raw Ed25519 bytes.
    For non-did:key identifiers, returns the validated supplied hex (or None).
    """
    derived = try_public_key_from_did(did)
    if derived is not None:
        derived_hex = public_key_hex(derived)
        if supplied_hex:
            if supplied_hex.strip().lower() != derived_hex:
                raise SignatureError(
                    "public_key does not match the Ed25519 key embedded in did:key"
                )
        return derived_hex
    if supplied_hex:
        return parse_public_key_hex(supplied_hex).hex()
    return None


def generate_keypair() -> tuple[bytes, bytes]:
    """Return (private_raw_32, public_raw_32). Caller stores private material."""
    private = Ed25519PrivateKey.generate()
    return private.private_bytes_raw(), private.public_key().public_bytes_raw()


def public_key_hex(public_raw: bytes) -> str:
    if len(public_raw) != 32:
        raise SignatureError("Ed25519 public key must be 32 bytes")
    return public_raw.hex()


def private_key_hex(private_raw: bytes) -> str:
    if len(private_raw) != 32:
        raise SignatureError("Ed25519 private key must be 32 bytes")
    return private_raw.hex()


def parse_public_key_hex(value: str) -> bytes:
    try:
        raw = bytes.fromhex(value.strip())
    except ValueError as exc:
        raise SignatureError("public_key must be hex-encoded Ed25519") from exc
    if len(raw) != 32:
        raise SignatureError("Ed25519 public key must be 32 bytes")
    try:
        Ed25519PublicKey.from_public_bytes(raw)
    except Exception as exc:  # noqa: BLE001
        raise SignatureError("invalid Ed25519 public key") from exc
    return raw


def canonical_message_bytes(
    *,
    message_id: str,
    type: str,
    from_agent: str,
    to_agent: str,
    timestamp: str,
    task_id: str | None,
    payload: dict[str, Any] | None,
) -> bytes:
    """Deterministic JSON: sorted keys, no extra whitespace, UTF-8.

    Signature covers public fields only. The `signature` field itself is excluded.
    """
    body = {
        "from": from_agent,
        "message_id": message_id,
        "payload": payload or {},
        "task_id": task_id,
        "timestamp": timestamp,
        "to": to_agent,
        "type": type,
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def sign(private_raw: bytes, message: bytes) -> str:
    """Return hex-encoded 64-byte Ed25519 signature. Does not log the key."""
    if len(private_raw) != 32:
        raise SignatureError("Ed25519 private key must be 32 bytes")
    key = Ed25519PrivateKey.from_private_bytes(private_raw)
    return key.sign(message).hex()


def verify(public_raw: bytes, message: bytes, signature_hex: str) -> bool:
    if len(public_raw) != 32:
        return False
    try:
        sig = bytes.fromhex(signature_hex.strip())
    except ValueError:
        return False
    if len(sig) != 64:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(public_raw).verify(sig, message)
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


def verify_or_raise(public_raw: bytes, message: bytes, signature_hex: str) -> None:
    if not verify(public_raw, message, signature_hex):
        raise SignatureError("invalid Ed25519 signature")


class TechnocoreDidAdapter:
    """Hook for a future Technocore DID resolver.

    Default implementation returns None so the registry uses the public_key
    stored on the agent profile (generic Ed25519). Do not invent Technocore APIs.
    """

    def resolve_public_key(self, did: str) -> bytes | None:  # noqa: ARG002
        return None


default_did_adapter = TechnocoreDidAdapter()


def resolve_verify_key(did: str, profile_public_key_hex: str | None) -> bytes | None:
    """Prefer adapter, then profile hex, then derive from did:key when possible."""
    resolved = default_did_adapter.resolve_public_key(did)
    if resolved:
        return resolved
    if profile_public_key_hex:
        return parse_public_key_hex(profile_public_key_hex)
    derived = try_public_key_from_did(did)
    if derived is not None:
        return derived
    return None
