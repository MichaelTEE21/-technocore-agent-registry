"""Public-profile proof snapshots. Never include private keys, seeds, or PEMs."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

PROOF_TYPE = "tar.proof.profile.v1"
PROOF_DISCLAIMER = (
    "Local registry snapshot. Not an official Technocore attestation. "
    "Not a token or airdrop claim. Public data only."
)

_FORBIDDEN_FIELD_NAMES = {
    "privatekey",
    "private_key",
    "secret",
    "secretkey",
    "secret_key",
    "seed",
    "mnemonic",
    "identity_pem",
    "privkey",
    "sk",
}


def _iso_z(now: datetime | None = None) -> str:
    stamp = now or datetime.now(UTC)
    return stamp.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    """UTF-8 JSON with sorted object keys. Used only for public fields."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def hash_public_fields(fields: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(fields).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def capability_public_dict(cap: Any) -> dict[str, str]:
    """id / category / level / evidence_status — no other fields."""
    if hasattr(cap, "model_dump"):
        data = cap.model_dump()
        cap_id = data.get("id") or data.get("capability_id")
        return {
            "id": str(cap_id),
            "category": str(data.get("category") or ""),
            "level": str(data.get("level") or "intermediate"),
            "evidence_status": str(data.get("evidence_status") or "claimed"),
        }
    if isinstance(cap, dict):
        cap_id = cap.get("id") or cap.get("capability_id")
        return {
            "id": str(cap_id),
            "category": str(cap.get("category") or ""),
            "level": str(cap.get("level") or "intermediate"),
            "evidence_status": str(cap.get("evidence_status") or "claimed"),
        }
    cap_id = getattr(cap, "id", None) or getattr(cap, "capability_id", "")
    return {
        "id": str(cap_id),
        "category": str(getattr(cap, "category", "") or ""),
        "level": str(getattr(cap, "level", None) or "intermediate"),
        "evidence_status": str(getattr(cap, "evidence_status", None) or "claimed"),
    }


def public_profile_fields(
    *,
    did: str,
    found: bool,
    agent_id: str | None,
    name: str | None,
    capabilities: list[Any] | None,
    verification: dict[str, str] | None,
    public_key: str | None,
) -> dict[str, Any]:
    caps = [capability_public_dict(c) for c in (capabilities or [])]
    ver: dict[str, str] | None = None
    if verification is not None:
        status = verification.get("status") if isinstance(verification, dict) else None
        if status:
            ver = {"status": str(status)}
    return {
        "did": did,
        "found": found,
        "agent_id": agent_id,
        "name": name,
        "capabilities": caps,
        "verification": ver,
        "public_key": public_key,
    }


def _assert_public_only(obj: Any) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            compact = str(key).lower().replace("-", "_")
            if compact in _FORBIDDEN_FIELD_NAMES:
                raise ValueError("private keys and secrets are not included in proofs")
            _assert_public_only(value)
    elif isinstance(obj, list):
        for item in obj:
            _assert_public_only(item)
    elif isinstance(obj, str):
        lower = obj.lower()
        if "-----begin" in lower or "private key" in lower:
            raise ValueError("private keys and secrets are not included in proofs")


def build_proof_document(
    *,
    did: str,
    found: bool,
    agent_id: str | None = None,
    name: str | None = None,
    capabilities: list[Any] | None = None,
    verification: dict[str, str] | None = None,
    public_key: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Versioned public-profile proof. Hash covers public fields only (sorted keys)."""
    fields = public_profile_fields(
        did=did,
        found=found,
        agent_id=agent_id,
        name=name,
        capabilities=capabilities,
        verification=verification,
        public_key=public_key,
    )
    stamp = generated_at or _iso_z()
    doc: dict[str, Any] = {
        "type": PROOF_TYPE,
        "did": fields["did"],
        "found": fields["found"],
        "agent_id": fields["agent_id"],
        "name": fields["name"],
        "capabilities": fields["capabilities"],
        "verification": fields["verification"],
        "public_key": fields["public_key"],
        "generated_at": stamp,
        "content_hash": hash_public_fields(fields),
        "disclaimer": PROOF_DISCLAIMER,
    }
    _assert_public_only(doc)
    return doc
