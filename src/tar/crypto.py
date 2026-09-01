"""Ed25519 sign/verify for local A2A messages.

Private keys never enter the registry database, logs, or printed output.
They live only in demo agent processes or gitignored temp files.

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


class SignatureError(ValueError):
    """Invalid key material or signature."""


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
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


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
    resolved = default_did_adapter.resolve_public_key(did)
    if resolved:
        return resolved
    if profile_public_key_hex:
        return parse_public_key_hex(profile_public_key_hex)
    return None
