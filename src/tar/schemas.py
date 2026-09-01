"""Pydantic v2 request/response models. Extra fields are ignored (evolvable schema)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from tar.identity import IdentityError, default_identity_provider
from tar.taxonomy import LEVELS, known_capability_ids, known_category_ids

AgentStatus = Literal["online", "busy", "offline", "unknown"]
VerificationStatus = Literal[
    "claimed", "verified", "community-verified", "expired", "disputed"
]
VerificationKind = Literal["claim", "evidence", "dispute"]
ReputationEventType = Literal[
    "task_completed",
    "task_failed",
    "verification_success",
    "verification_failure",
    "community_endorsement",
    "dispute",
]

# Client payloads must never carry key material. Reject these names anywhere.
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


class IgnoreExtras(BaseModel):
    model_config = ConfigDict(extra="ignore")


class CapabilityClaim(IgnoreExtras):
    id: str = Field(min_length=1, max_length=128)
    category: str = Field(min_length=1, max_length=64)
    level: str = Field(default="intermediate", max_length=32)

    @field_validator("id")
    @classmethod
    def cap_known(cls, value: str) -> str:
        if value not in known_capability_ids():
            raise ValueError(f"unknown capability id: {value}")
        return value

    @field_validator("category")
    @classmethod
    def cat_known(cls, value: str) -> str:
        if value not in known_category_ids():
            raise ValueError(f"unknown category: {value}")
        return value

    @field_validator("level")
    @classmethod
    def level_known(cls, value: str) -> str:
        if value not in LEVELS:
            raise ValueError(f"level must be one of {LEVELS}")
        return value


class VerificationBlock(IgnoreExtras):
    status: VerificationStatus = "claimed"


class AgentCreate(IgnoreExtras):
    id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    name: str = Field(min_length=1, max_length=256)
    did: str = Field(min_length=8, max_length=512)
    version: str = Field(default="0.1.0", max_length=64)
    description: str = Field(default="", max_length=4000)
    capabilities: list[CapabilityClaim] = Field(default_factory=list, max_length=64)
    protocols: list[str] = Field(default_factory=lambda: ["http"], max_length=16)
    status: AgentStatus = "unknown"
    endpoint: str | None = Field(default=None, max_length=1024)
    verification: VerificationBlock = Field(default_factory=VerificationBlock)
    fictional: bool = True

    @field_validator("did")
    @classmethod
    def public_did_only(cls, value: str) -> str:
        try:
            return default_identity_provider.validate_public_did(value)
        except IdentityError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("endpoint")
    @classmethod
    def endpoint_shape(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError("endpoint must be an http(s) URL")
        return value

    @model_validator(mode="before")
    @classmethod
    def reject_key_material(cls, data: Any) -> Any:
        _assert_no_secrets(data)
        return data

    @model_validator(mode="after")
    def caps_match_category(self) -> AgentCreate:
        from tar.taxonomy import CAPABILITY_INDEX

        for cap in self.capabilities:
            expected = CAPABILITY_INDEX[cap.id]["category"]
            if cap.category != expected:
                raise ValueError(
                    f"capability {cap.id} belongs to category {expected}, not {cap.category}"
                )
        if self.verification.status == "verified":
            # Registration never auto-verifies.
            self.verification.status = "claimed"
        return self


class AgentUpdate(IgnoreExtras):
    name: str | None = Field(default=None, max_length=256)
    version: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=4000)
    capabilities: list[CapabilityClaim] | None = None
    protocols: list[str] | None = None
    status: AgentStatus | None = None
    endpoint: str | None = Field(default=None, max_length=1024)

    @model_validator(mode="before")
    @classmethod
    def reject_key_material(cls, data: Any) -> Any:
        _assert_no_secrets(data)
        return data


class AgentOut(IgnoreExtras):
    id: str
    name: str
    did: str
    version: str
    description: str
    capabilities: list[CapabilityClaim]
    protocols: list[str]
    status: AgentStatus
    endpoint: str | None
    verification: VerificationBlock
    fictional: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(extra="ignore", from_attributes=True)


class AgentList(IgnoreExtras):
    items: list[AgentOut]
    count: int


class VerificationCreate(IgnoreExtras):
    """POST records a claim, evidence pointer, or dispute. Never auto-verifies."""

    kind: VerificationKind
    summary: str = Field(default="", max_length=2000)
    evidence_uri: str | None = Field(default=None, max_length=1024)

    @model_validator(mode="before")
    @classmethod
    def reject_key_material(cls, data: Any) -> Any:
        _assert_no_secrets(data)
        return data


class VerificationOut(IgnoreExtras):
    id: int
    agent_id: str
    kind: str
    status: VerificationStatus
    summary: str
    evidence_uri: str | None
    created_at: datetime


class VerificationList(IgnoreExtras):
    agent_id: str
    current_status: VerificationStatus
    note: str = (
        "claimed vs evidence vs verified are distinct. "
        "This registry records claims and evidence; it does not auto-verify."
    )
    items: list[VerificationOut]


class CapabilityOut(IgnoreExtras):
    id: str
    name: str
    category: str
    category_name: str | None = None
    description: str
    disclaimer: str | None = None


class CategoryOut(IgnoreExtras):
    id: str
    name: str
    description: str
    disclaimer: str | None = None
    capabilities: list[dict[str, Any]]


class SwarmCreate(IgnoreExtras):
    id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    name: str = Field(min_length=1, max_length=256)
    description: str = Field(default="", max_length=4000)
    member_agent_ids: list[str] = Field(default_factory=list, max_length=256)
    required_capabilities: list[str] = Field(default_factory=list, max_length=64)

    @field_validator("required_capabilities")
    @classmethod
    def caps_known(cls, values: list[str]) -> list[str]:
        known = known_capability_ids()
        for item in values:
            if item not in known:
                raise ValueError(f"unknown capability id: {item}")
        return values

    @model_validator(mode="before")
    @classmethod
    def reject_key_material(cls, data: Any) -> Any:
        _assert_no_secrets(data)
        return data


class SwarmMemberAdd(IgnoreExtras):
    agent_id: str = Field(min_length=1, max_length=128)


class SwarmOut(IgnoreExtras):
    id: str
    name: str
    description: str
    member_agent_ids: list[str]
    required_capabilities: list[str]
    proposed: bool = False
    persisted: bool = True
    note: str | None = None
    members: list[AgentOut] | None = None


class SwarmList(IgnoreExtras):
    items: list[SwarmOut]
    count: int


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    error: dict[str, str]


class HealthOut(IgnoreExtras):
    status: str = "ok"
    version: str
    service: str = "technocore-agent-registry"


def _assert_no_secrets(data: Any) -> None:
    if isinstance(data, dict):
        for key, value in data.items():
            compact = str(key).lower().replace("-", "_")
            if compact in _FORBIDDEN_FIELD_NAMES:
                raise ValueError("private keys and secrets are not accepted")
            _assert_no_secrets(value)
    elif isinstance(data, list):
        for item in data:
            _assert_no_secrets(item)
    elif isinstance(data, str):
        lower = data.lower()
        if "-----begin" in lower or "private key" in lower:
            raise ValueError("private keys and secrets are not accepted")
