"""Agent-to-agent message types and local registry envelopes.

This is a local log of REQUEST / ACCEPT / REJECT / PROGRESS / RESULT / VERIFY
messages. It is not a live decentralized network. Delivery to remote hosts is
out of scope; peers read and write the registry.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
        "the sender public_key. Not a live mesh."
    )


class A2ATransport:
    """Optional adapter a future transport could implement. Unused for delivery."""

    def send(self, envelope: A2AEnvelope) -> None:  # noqa: ARG002
        raise NotImplementedError("No remote A2A transport in this reference implementation.")

    def poll(self, agent_id: str) -> list[A2AEnvelope]:  # noqa: ARG002
        raise NotImplementedError("No remote A2A transport in this reference implementation.")
