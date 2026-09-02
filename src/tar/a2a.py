"""Agent-to-agent message types and local registry envelopes.

This is a local log of REQUEST / ACCEPT / REJECT / PROGRESS / RESULT / VERIFY
messages. It is not a live decentralized network. Delivery to remote hosts is
out of scope; peers read and write the registry.

Disclaimer: Not an official FLOP protocol. Structure is registry-mediated A2A
suitable for later FLOP adaptation when that spec lands — do not claim FLOP.
No outbound HTTP to agent endpoints in this MVP (registry-mediated only).
No private keys are stored or transmitted by this module.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

PROTOCOL_NAME = "tar.a2a"
PROTOCOL_VERSION = "1.0"

# Documented aliases for other-language clients. This registry speaks the enum values.
# SUBMIT is a product-brief alias for RESULT (task.submit → RESULT).
MESSAGE_TYPE_ALIASES = {
    "task.request": "REQUEST",
    "task.accept": "ACCEPT",
    "task.reject": "REJECT",
    "task.progress": "PROGRESS",
    "task.result": "RESULT",
    "task.submit": "RESULT",  # SUBMIT naming ≡ RESULT
    "task.verify": "VERIFY",
    "SUBMIT": "RESULT",
}


# ---------------------------------------------------------------------------
# FLOP_ADAPTATION
# This registry-mediated A2A can later map to FLOP when the official FLOP
# interop spec lands. Do not claim this implementation *is* FLOP.
# Mapping sketch (stub only):
#   REQUEST  → flop.task.request (or equivalent)
#   ACCEPT   → flop.task.accept
#   REJECT   → flop.task.reject
#   PROGRESS → flop.task.progress
#   RESULT / SUBMIT → flop.task.result
#   VERIFY   → flop.task.verify
# Transport remains registry-mediated until a FLOP peer transport exists.
# ---------------------------------------------------------------------------
FLOP_ADAPTATION = {
    "status": "stub",
    "claim": "not_official_flop",
    "note": (
        "Registry-mediated A2A structured for later FLOP adaptation. "
        "Do not assert FLOP compliance until the FLOP specification lands "
        "and ProtocolAdapter is implemented against it."
    ),
    "message_map": {
        "REQUEST": "flop.task.request",
        "ACCEPT": "flop.task.accept",
        "REJECT": "flop.task.reject",
        "PROGRESS": "flop.task.progress",
        "RESULT": "flop.task.result",
        "VERIFY": "flop.task.verify",
    },
}


class A2AMessageType(str, Enum):
    REQUEST = "REQUEST"
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    PROGRESS = "PROGRESS"
    RESULT = "RESULT"
    VERIFY = "VERIFY"


class A2AEnvelope(BaseModel):
    """Signed envelope stored by this local registry."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    message_id: str
    type: A2AMessageType
    from_agent: str = Field(alias="from")
    to_agent: str = Field(alias="to")
    timestamp: str
    task_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    signature: str | None = None
    note: str = (
        "Local registry message. Generic Ed25519 signatures bind the envelope to "
        "the sender public_key. Not a live mesh. Not official FLOP."
    )


class A2ATransport:
    """Optional adapter a future transport could implement. Unused for delivery.

    MVP rule: no outbound HTTP to agent endpoints — registry-mediated only.
    """

    def send(self, envelope: A2AEnvelope) -> None:  # noqa: ARG002
        raise NotImplementedError("No remote A2A transport in this reference implementation.")

    def poll(self, agent_id: str) -> list[A2AEnvelope]:  # noqa: ARG002
        raise NotImplementedError("No remote A2A transport in this reference implementation.")


class ProtocolAdapter:
    """Stub for future FLOP (or other) protocol mapping.

    Intentionally unimplemented. When FLOP lands, map MESSAGE_TYPE_ALIASES /
    A2AMessageType through FLOP_ADAPTATION['message_map'] without claiming
    FLOP compliance until verified against the published spec.
    """

    def to_external(self, message_type: str) -> str:
        """Map internal type to an external protocol label (stub)."""
        canonical = MESSAGE_TYPE_ALIASES.get(message_type, message_type)
        return FLOP_ADAPTATION["message_map"].get(canonical, canonical)

    def from_external(self, external_type: str) -> str:
        """Map external label back to internal RESULT/REQUEST/… (stub)."""
        reverse = {v: k for k, v in FLOP_ADAPTATION["message_map"].items()}
        return reverse.get(external_type, external_type)
