"""ORM <-> API helpers."""

from __future__ import annotations

import json

from tar.models import (
    Agent,
    Contribution,
    Message,
    Swarm,
    Task,
    VerificationRecord,
    utcnow,
)
from tar.schemas import (
    AgentOut,
    CapabilityClaim,
    ContributionOut,
    MessageOut,
    RankedAgent,
    SwarmOut,
    TaskOut,
    VerificationBlock,
    VerificationOut,
)


def agent_to_out(agent: Agent) -> AgentOut:
    protocols = json.loads(agent.protocols_json or "[]")
    caps = [
        CapabilityClaim(
            id=c.capability_id,
            category=c.category,
            level=c.level,
            evidence_status=getattr(c, "evidence_status", None) or "claimed",  # type: ignore[arg-type]
        )
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
        public_key=agent.public_key,
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
    recommended: list[RankedAgent] | None = None,
    executing: list[RankedAgent] | None = None,
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
        recommended=recommended,
        executing=executing,
    )


def verification_to_out(row: VerificationRecord) -> VerificationOut:
    return VerificationOut(
        id=row.id,
        agent_id=row.agent_id,
        kind=row.kind,
        status=row.status,  # type: ignore[arg-type]
        summary=row.summary,
        evidence_uri=row.evidence_uri,
        capability_id=row.capability_id,
        checker_id=row.checker_id,
        created_at=row.created_at,
    )


def task_to_out(task: Task) -> TaskOut:
    result = None
    if task.result_json:
        try:
            result = json.loads(task.result_json)
        except json.JSONDecodeError:
            result = {"raw": task.result_json}
    return TaskOut(
        task_id=task.id,
        requester=task.requester_id,
        assignee=task.assignee_id,
        target_agent_id=task.assignee_id,
        requested_capability=task.requested_capability,
        description=task.description,
        status=task.status,  # type: ignore[arg-type]
        protocol=task.protocol,
        result=result,
        accepted_at=getattr(task, "accepted_at", None),
        completed_at=getattr(task, "completed_at", None),
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def message_to_out(row: Message) -> MessageOut:
    try:
        payload = json.loads(row.payload_json or "{}")
    except json.JSONDecodeError:
        payload = {}
    return MessageOut(
        message_id=row.message_id,
        type=row.type,  # type: ignore[arg-type]
        from_agent=row.from_agent,
        to_agent=row.to_agent,
        timestamp=row.timestamp,
        task_id=row.task_id,
        payload=payload,
        signature=row.signature,
    )


def contribution_to_out(row: Contribution) -> ContributionOut:
    return ContributionOut(
        id=row.id,
        agent=row.agent_id,
        event=row.event,
        timestamp=row.created_at,
        task=row.task_id,
        reference=row.reference,
        verification_state=row.verification_state,
        detail=row.detail,
    )


def touch(agent: Agent) -> None:
    agent.updated_at = utcnow()
