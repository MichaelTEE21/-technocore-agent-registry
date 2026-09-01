"""ORM <-> API helpers."""

from __future__ import annotations

import json

from tar.models import Agent, Swarm, VerificationRecord, utcnow
from tar.schemas import (
    AgentOut,
    CapabilityClaim,
    SwarmOut,
    VerificationBlock,
    VerificationOut,
)


def agent_to_out(agent: Agent) -> AgentOut:
    protocols = json.loads(agent.protocols_json or "[]")
    caps = [
        CapabilityClaim(id=c.capability_id, category=c.category, level=c.level)
        for c in agent.capabilities
    ]
    return AgentOut(
        id=agent.id,
        name=agent.name,
        did=agent.did,
        version=agent.version,
        description=agent.description,
        capabilities=caps,
        protocols=protocols,
        status=agent.status,  # type: ignore[arg-type]
        endpoint=agent.endpoint,
        verification=VerificationBlock(status=agent.verification_status),  # type: ignore[arg-type]
        fictional=agent.fictional.lower() != "false",
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


def swarm_to_out(
    swarm: Swarm,
    *,
    members: list[AgentOut] | None = None,
    proposed: bool = False,
    persisted: bool = True,
    note: str | None = None,
) -> SwarmOut:
    required = json.loads(swarm.required_capabilities_json or "[]")
    ids = [m.agent_id for m in swarm.members]
    return SwarmOut(
        id=swarm.id,
        name=swarm.name,
        description=swarm.description,
        member_agent_ids=ids,
        required_capabilities=required,
        proposed=proposed,
        persisted=persisted,
        note=note,
        members=members,
    )


def verification_to_out(row: VerificationRecord) -> VerificationOut:
    return VerificationOut(
        id=row.id,
        agent_id=row.agent_id,
        kind=row.kind,
        status=row.status,  # type: ignore[arg-type]
        summary=row.summary,
        evidence_uri=row.evidence_uri,
        created_at=row.created_at,
    )


def touch(agent: Agent) -> None:
    agent.updated_at = utcnow()
