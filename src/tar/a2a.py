"""Agent-to-agent message *shapes* for a future task protocol.

This module is not a messaging network. It defines REQUEST / ACCEPT / REJECT /
PROGRESS / RESULT / VERIFY envelopes so clients can agree on types later.
Runtime delivery, inbox, and task delegation are FUTURE.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class A2AMessageType(str, Enum):
    REQUEST = "REQUEST"
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    PROGRESS = "PROGRESS"
    RESULT = "RESULT"
    VERIFY = "VERIFY"


class A2AEnvelope(BaseModel):
    """Typed envelope. Not transported by this registry."""

    model_config = ConfigDict(extra="ignore")

    type: A2AMessageType
    from_agent: str
    to_agent: str
    task_id: str | None = None
    capability: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    note: str = "FUTURE: this registry does not deliver A2A messages."


class A2ATransport(Protocol):
    """Interface a future messaging layer would implement. Unused in v0.1."""

    def send(self, envelope: A2AEnvelope) -> None: ...

    def poll(self, agent_id: str) -> list[A2AEnvelope]: ...
