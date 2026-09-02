"""Pydantic v2 request/response models. Extra fields are ignored (evolvable schema)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from tar.crypto import SignatureError, parse_public_key_hex
from tar.identity import IdentityError, default_identity_provider
from tar.taxonomy import LEVELS, known_capability_ids, known_category_ids

AgentStatus = Literal["online", "busy", "offline", "unknown"]
VerificationStatus = Literal[
    "claimed",
    "independently-checked",
    "vouched",
    "verified",
    "community-verified",
    "expired",
    "disputed",
]
EvidenceStatus = Literal[
    "claimed", "verified", "community-verified", "expired", "disputed"
]
VerificationKind = Literal[
    "claim", "evidence", "dispute", "independently-checked", "vouch"
]
TaskStatus = Literal[
    "requested",
    "accepted",
    "rejected",
    "in_progress",
    "completed",
    "failed",
    "verified",
    "disputed",
]
MessageType = Literal["REQUEST", "ACCEPT", "REJECT", "PROGRESS", "RESULT", "VERIFY"]
ContributionEvent = Literal[
    "task_completed",
    "task_failed",
    "result_verified",
    "capability_verified",
    "community_endorsement",
    "dispute",
    "profile_proof_generated",
]
ReputationEventType = Literal[
    "task_completed",
    "task_failed",
    "verification_success",
    "verification_failure",
    "community_endorsement",
    "dispute",
    "result_verified",
    "capability_verified",
    "profile_proof_generated",
]

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
    evidence_status: EvidenceStatus = "claimed"

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
    version: str = Field(default="1.0.0", max_length=64)
    description: str = Field(default="", max_length=4000)
    capabilities: list[CapabilityClaim] = Field(default_factory=list, max_length=64)
    protocols: list[str] = Field(default_factory=lambda: ["http"], max_length=16)
    status: AgentStatus = "unknown"
    endpoint: str | None = Field(default=None, max_length=1024)
    verification: VerificationBlock = Field(default_factory=VerificationBlock)
    public_key: str | None = Field(
        default=None,
        max_length=128,
        description="Ed25519 public key as lowercase hex (32 bytes). Derived from did:key when possible.",
    )
    fictional: bool = Field(
        default=False,
        description=(
            "True for demo/fictional agents. Defaults false for real registrations; "
            "did:example: DIDs are always treated as fictional."
        ),
    )

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

    @field_validator("public_key")
    @classmethod
    def public_key_ed25519(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        try:
            return parse_public_key_hex(value).hex()
        except SignatureError as exc:
            raise ValueError(str(exc)) from exc

    @model_validator(mode="before")
    @classmethod
    def reject_key_material(cls, data: Any) -> Any:
        _assert_no_secrets(data)
        return data

    @model_validator(mode="after")
    def caps_match_category(self) -> AgentCreate:
        from tar.crypto import SignatureError as SigErr
        from tar.crypto import resolve_registration_public_key
        from tar.identity import is_demo_did
        from tar.taxonomy import CAPABILITY_INDEX

        for cap in self.capabilities:
            expected = CAPABILITY_INDEX[cap.id]["category"]
            if cap.category != expected:
                raise ValueError(
                    f"capability {cap.id} belongs to category {expected}, not {cap.category}"
                )
            cap.evidence_status = "claimed"
        if self.verification.status in {"verified", "vouched", "independently-checked"}:
            self.verification.status = "claimed"
        # Prefer derive from did:key; reject mismatched supplied public_key.
        try:
            self.public_key = resolve_registration_public_key(self.did, self.public_key)
        except SigErr as exc:
            raise ValueError(str(exc)) from exc
        # Demo DIDs are always fictional; non-demo default remains false unless flagged.
        if is_demo_did(self.did):
            self.fictional = True
        return self


class AgentUpdate(IgnoreExtras):
    """Whitelist of public metadata fields. No credentials or arbitrary injection."""

    name: str | None = Field(default=None, min_length=1, max_length=256)
    did: str | None = Field(default=None, min_length=8, max_length=512)
    version: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=4000)
    capabilities: list[CapabilityClaim] | None = None
    protocols: list[str] | None = Field(default=None, max_length=16)
    status: AgentStatus | None = None
    endpoint: str | None = Field(default=None, max_length=1024)
    public_key: str | None = Field(default=None, max_length=128)
    fictional: bool | None = None

    @field_validator("did")
    @classmethod
    def public_did_only(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        try:
            return default_identity_provider.validate_public_did(value)
        except IdentityError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("endpoint")
    @classmethod
    def endpoint_shape(cls, value: str | None) -> str | None:
        # Empty string clears the endpoint. Do not fetch/call the URL.
        if value is None or value == "":
            return None
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError("endpoint must be an http(s) URL")
        return value

    @field_validator("public_key")
    @classmethod
    def public_key_ed25519(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        try:
            return parse_public_key_hex(value).hex()
        except SignatureError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("protocols")
    @classmethod
    def protocols_shape(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [str(p).strip() for p in value if str(p).strip()]
        if len(cleaned) > 16:
            raise ValueError("at most 16 protocols")
        return cleaned

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
    public_key: str | None = None
    fictional: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(extra="ignore", from_attributes=True)


class AgentList(IgnoreExtras):
    items: list[AgentOut]
    count: int
    total: int | None = None
    limit: int | None = None
    offset: int | None = None


class VerificationCreate(IgnoreExtras):
    """POST records a claim, evidence pointer, independent check, vouch, or dispute.

    Evidence never auto-promotes to verified. Vouch requires a prior independent check.
    """

    kind: VerificationKind
    summary: str = Field(default="", max_length=2000)
    evidence_uri: str | None = Field(default=None, max_length=1024)
    capability_id: str | None = Field(default=None, max_length=128)
    checker_id: str | None = Field(default=None, max_length=128)

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
    capability_id: str | None = None
    checker_id: str | None = None
    created_at: datetime


class VerificationList(IgnoreExtras):
    agent_id: str
    current_status: VerificationStatus
    note: str = (
        "Credence is TASK → ACCEPT → SUBMIT → VOUCH. "
        "CLAIMED ≠ VERIFIED ≠ VOUCHED: claims are self-asserted; "
        "independently-checked means a third party re-ran; vouched requires that prior check. "
        "This registry records claims and evidence; it does not auto-verify capability claims."
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
    role: Literal["recommended", "executing"] = "recommended"


class SwarmPropose(IgnoreExtras):
    capabilities: list[str] = Field(min_length=1, max_length=32)
    protocol: str | None = Field(default=None, max_length=64)
    persist: bool = False
    id: str | None = Field(default=None, max_length=128)
    name: str | None = Field(default=None, max_length=256)

    @field_validator("capabilities")
    @classmethod
    def caps_known(cls, values: list[str]) -> list[str]:
        known = known_capability_ids()
        for item in values:
            if item not in known:
                raise ValueError(f"unknown capability id: {item}")
        return values


class RankBreakdown(IgnoreExtras):
    capability_match: float
    verification_status: float
    availability: float
    compatibility: float
    evidence: float


class RankedAgent(IgnoreExtras):
    agent: AgentOut
    rank: float
    rank_breakdown: RankBreakdown
    matched_capabilities: list[str] = Field(default_factory=list)
    role: Literal["recommended", "executing"] | None = None


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
    recommended: list[RankedAgent] | None = None
    executing: list[RankedAgent] | None = None


class SwarmList(IgnoreExtras):
    items: list[SwarmOut]
    count: int


class DiscoverOut(IgnoreExtras):
    capabilities: list[str]
    items: list[RankedAgent]
    count: int
    ranking: dict[str, Any]


class TaskCreate(IgnoreExtras):
    requester: str = Field(min_length=1, max_length=128)
    requested_capability: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=8000)
    assignee: str | None = Field(default=None, max_length=128)
    protocol: str = Field(default="http", max_length=64)
    task_id: str | None = Field(default=None, max_length=128)

    @field_validator("requested_capability")
    @classmethod
    def cap_known(cls, value: str) -> str:
        if value not in known_capability_ids():
            raise ValueError(f"unknown capability id: {value}")
        return value

    @model_validator(mode="before")
    @classmethod
    def reject_key_material(cls, data: Any) -> Any:
        _assert_no_secrets(data)
        return data


class TaskAction(IgnoreExtras):
    agent_id: str = Field(min_length=1, max_length=128)
    message_id: str | None = Field(default=None, max_length=128)
    timestamp: str | None = Field(default=None, max_length=64)
    signature: str | None = Field(default=None, max_length=256)
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def reject_key_material(cls, data: Any) -> Any:
        _assert_no_secrets(data)
        return data


class TaskResultAction(TaskAction):
    result: dict[str, Any] | str | None = None


class TaskOut(IgnoreExtras):
    task_id: str
    requester: str
    assignee: str | None
    requested_capability: str
    description: str
    status: TaskStatus
    protocol: str
    result: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaskList(IgnoreExtras):
    items: list[TaskOut]
    count: int
    total: int | None = None
    limit: int | None = None
    offset: int | None = None


class MessageCreate(IgnoreExtras):
    message_id: str = Field(min_length=1, max_length=128)
    type: MessageType
    from_agent: str = Field(alias="from", min_length=1, max_length=128)
    to_agent: str = Field(alias="to", min_length=1, max_length=128)
    timestamp: str = Field(min_length=1, max_length=64)
    task_id: str | None = Field(default=None, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    signature: str | None = Field(default=None, max_length=256)

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def reject_key_material(cls, data: Any) -> Any:
        _assert_no_secrets(data)
        return data


class MessageOut(IgnoreExtras):
    message_id: str
    type: MessageType
    from_agent: str = Field(alias="from")
    to_agent: str = Field(alias="to")
    timestamp: str
    task_id: str | None
    payload: dict[str, Any]
    signature: str | None = None

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class MessageList(IgnoreExtras):
    items: list[MessageOut]
    count: int


class ContributionCreate(IgnoreExtras):
    agent_id: str = Field(min_length=1, max_length=128)
    event: ContributionEvent
    task_id: str | None = Field(default=None, max_length=128)
    reference: str | None = Field(default=None, max_length=1024)
    verification_state: VerificationStatus = "claimed"
    detail: str = Field(default="", max_length=2000)

    @model_validator(mode="before")
    @classmethod
    def reject_key_material(cls, data: Any) -> Any:
        _assert_no_secrets(data)
        return data


class ContributionOut(IgnoreExtras):
    id: int
    agent: str
    event: str
    timestamp: datetime
    task: str | None = None
    reference: str | None = None
    verification_state: str
    detail: str = ""


class ContributionList(IgnoreExtras):
    items: list[ContributionOut]
    count: int


class MetricsOut(IgnoreExtras):
    agent_id: str
    tasks_completed: int
    tasks_failed: int
    results_verified: int
    verification_rate: float
    capabilities_claimed: int
    capabilities_verified: int
    contributions_recorded: int
    note: str = (
        "These are counts, not a reputation score and not professional qualifications. "
        "A future release may derive a documented reputation idea from the same events; "
        "v1.0.0 does not."
    )


class LookupOut(IgnoreExtras):
    found: bool
    did: str
    format: Literal["ok"] = "ok"
    agent: AgentOut | None = None
    capabilities: list[CapabilityClaim] = Field(default_factory=list)
    message: str | None = None


class ProofOut(IgnoreExtras):
    type: Literal["tar.proof.profile.v1"] = "tar.proof.profile.v1"
    did: str
    found: bool
    agent_id: str | None = None
    name: str | None = None
    capabilities: list[CapabilityClaim] = Field(default_factory=list)
    verification: VerificationBlock | None = None
    public_key: str | None = None
    generated_at: str
    content_hash: str
    disclaimer: str = (
        "Local registry snapshot. Not an official Technocore attestation. "
        "Not a token or airdrop claim. Public data only."
    )


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
