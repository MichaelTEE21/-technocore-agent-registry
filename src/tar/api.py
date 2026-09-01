"""REST API: agents, capabilities, verification, swarms."""

from __future__ import annotations

import json
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from tar.db import get_db
from tar.models import (
    Agent,
    AgentCapability,
    ReputationEvent,
    Swarm,
    SwarmMember,
    VerificationRecord,
    utcnow,
)
from tar.schemas import (
    AgentCreate,
    AgentList,
    AgentOut,
    AgentUpdate,
    CapabilityOut,
    SwarmCreate,
    SwarmList,
    SwarmMemberAdd,
    SwarmOut,
    VerificationCreate,
    VerificationList,
)
from tar.security import error_body, require_registry_token
from tar.serialize import agent_to_out, swarm_to_out, verification_to_out
from tar.taxonomy import all_categories, get_capability, list_capabilities

router = APIRouter()
Db = Annotated[Session, Depends(get_db)]
Auth = Annotated[None, Depends(require_registry_token)]

_ID_RE = re.compile(r"^[A-Za-z0-9._:-]+$")


def _http_error(code: int, slug: str, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail=error_body(slug, message)["error"])


def _get_agent(db: Session, agent_id: str) -> Agent:
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise _http_error(404, "not_found", f"agent not found: {agent_id}")
    return agent


def _replace_capabilities(db: Session, agent: Agent, claims) -> None:
    agent.capabilities.clear()
    db.flush()
    for claim in claims:
        agent.capabilities.append(
            AgentCapability(
                agent_id=agent.id,
                capability_id=claim.id,
                category=claim.category,
                level=claim.level,
            )
        )


@router.get("/healthz", tags=["meta"])
def healthz(request: Request) -> dict:
    version = getattr(request.app, "version", "0.1.0")
    return {"status": "ok", "version": version, "service": "technocore-agent-registry"}


@router.post(
    "/agents",
    status_code=status.HTTP_201_CREATED,
    response_model=AgentOut,
    tags=["agents"],
)
def register_agent(payload: AgentCreate, db: Db, _: Auth) -> AgentOut:
    if db.get(Agent, payload.id) is not None:
        raise _http_error(409, "conflict", f"agent id already registered: {payload.id}")
    existing_did = db.scalar(select(Agent).where(Agent.did == payload.did))
    if existing_did is not None:
        raise _http_error(409, "conflict", "DID already registered")
    agent = Agent(
        id=payload.id,
        name=payload.name,
        did=payload.did,
        version=payload.version,
        description=payload.description,
        protocols_json=json.dumps(payload.protocols),
        status=payload.status,
        endpoint=payload.endpoint,
        verification_status="claimed",
        fictional="true" if payload.fictional else "false",
    )
    db.add(agent)
    db.flush()
    _replace_capabilities(db, agent, payload.capabilities)
    db.add(
        VerificationRecord(
            agent_id=agent.id,
            kind="claim",
            status="claimed",
            summary="Registered; capabilities are self-claimed until evidence is recorded.",
        )
    )
    db.commit()
    db.refresh(agent)
    return agent_to_out(agent)


@router.get("/agents", response_model=AgentList, tags=["agents"])
def list_agents(
    db: Db,
    capability: str | None = Query(default=None),
    category: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
) -> AgentList:
    stmt = select(Agent).options(selectinload(Agent.capabilities)).order_by(Agent.id)
    if capability:
        stmt = stmt.join(AgentCapability).where(AgentCapability.capability_id == capability)
    if category:
        if capability:
            stmt = stmt.where(AgentCapability.category == category)
        else:
            stmt = stmt.join(AgentCapability).where(AgentCapability.category == category)
    if status_filter:
        if status_filter not in {"online", "busy", "offline", "unknown"}:
            raise _http_error(400, "bad_request", "status must be online|busy|offline|unknown")
        stmt = stmt.where(Agent.status == status_filter)
    stmt = stmt.distinct()
    agents = list(db.scalars(stmt).unique())
    items = [agent_to_out(a) for a in agents]
    return AgentList(items=items, count=len(items))


@router.get("/agents/{agent_id}", response_model=AgentOut, tags=["agents"])
def get_agent(agent_id: str, db: Db) -> AgentOut:
    agent = db.scalar(
        select(Agent).options(selectinload(Agent.capabilities)).where(Agent.id == agent_id)
    )
    if agent is None:
        raise _http_error(404, "not_found", f"agent not found: {agent_id}")
    return agent_to_out(agent)


@router.put("/agents/{agent_id}", response_model=AgentOut, tags=["agents"])
def update_agent(agent_id: str, payload: AgentUpdate, db: Db, _: Auth) -> AgentOut:
    agent = _get_agent(db, agent_id)
    if payload.name is not None:
        agent.name = payload.name
    if payload.version is not None:
        agent.version = payload.version
    if payload.description is not None:
        agent.description = payload.description
    if payload.protocols is not None:
        agent.protocols_json = json.dumps(payload.protocols)
    if payload.status is not None:
        agent.status = payload.status
    if payload.endpoint is not None:
        agent.endpoint = payload.endpoint
    if payload.capabilities is not None:
        _replace_capabilities(db, agent, payload.capabilities)
    agent.updated_at = utcnow()
    db.commit()
    db.refresh(agent)
    return agent_to_out(agent)


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["agents"])
def delete_agent(agent_id: str, db: Db, _: Auth) -> None:
    agent = _get_agent(db, agent_id)
    db.query(SwarmMember).filter(SwarmMember.agent_id == agent_id).delete()
    db.delete(agent)
    db.commit()
    return None


@router.get("/capabilities", tags=["capabilities"])
def get_capabilities(category: str | None = Query(default=None)) -> dict:
    if category:
        caps = list_capabilities(category)
        cats = [c for c in all_categories() if c["id"] == category]
        if not cats:
            raise _http_error(404, "not_found", f"category not found: {category}")
        return {"categories": cats, "items": caps, "count": len(caps)}
    cats = all_categories()
    items = list_capabilities()
    return {"categories": cats, "items": items, "count": len(items)}


@router.get("/capabilities/{capability_id}", response_model=CapabilityOut, tags=["capabilities"])
def get_one_capability(capability_id: str) -> CapabilityOut:
    cap = get_capability(capability_id)
    if cap is None:
        raise _http_error(404, "not_found", f"capability not found: {capability_id}")
    return CapabilityOut(**cap)


@router.get("/agents/{agent_id}/verification", response_model=VerificationList, tags=["verification"])
def get_verification(agent_id: str, db: Db) -> VerificationList:
    agent = _get_agent(db, agent_id)
    rows = list(
        db.scalars(
            select(VerificationRecord)
            .where(VerificationRecord.agent_id == agent_id)
            .order_by(VerificationRecord.created_at.desc())
        )
    )
    return VerificationList(
        agent_id=agent.id,
        current_status=agent.verification_status,  # type: ignore[arg-type]
        items=[verification_to_out(r) for r in rows],
    )


@router.post(
    "/agents/{agent_id}/verification",
    status_code=status.HTTP_201_CREATED,
    response_model=VerificationList,
    tags=["verification"],
)
def post_verification(agent_id: str, payload: VerificationCreate, db: Db, _: Auth) -> VerificationList:
    """Record a claim, evidence pointer, or dispute. Does not auto-verify."""
    agent = _get_agent(db, agent_id)
    if payload.kind == "dispute":
        stored_status = "disputed"
        agent.verification_status = "disputed"
    else:
        stored_status = "claimed"
        # Evidence does not promote to verified.
        if agent.verification_status not in {"disputed", "expired"}:
            agent.verification_status = "claimed"
    db.add(
        VerificationRecord(
            agent_id=agent.id,
            kind=payload.kind,
            status=stored_status,
            summary=payload.summary,
            evidence_uri=payload.evidence_uri,
        )
    )
    if payload.kind == "dispute":
        db.add(
            ReputationEvent(
                agent_id=agent.id,
                event_type="dispute",
                detail=payload.summary[:500],
            )
        )
    db.commit()
    return get_verification(agent_id, db)


@router.get("/swarms/assemble", response_model=SwarmOut, tags=["swarms"])
def assemble_swarm(
    db: Db,
    capability: str = Query(..., min_length=1),
) -> SwarmOut:
    """Propose a swarm of agents advertising `capability` with status online or unknown.

    Does not invent liveness. Status is whatever the client last reported.
    The proposal is not persisted.
    """
    cap = get_capability(capability)
    if cap is None:
        raise _http_error(404, "not_found", f"capability not found: {capability}")
    stmt = (
        select(Agent)
        .options(selectinload(Agent.capabilities))
        .join(AgentCapability)
        .where(AgentCapability.capability_id == capability)
        .where(Agent.status.in_(("online", "unknown")))
        .distinct()
        .order_by(Agent.id)
    )
    agents = list(db.scalars(stmt).unique())
    members = [agent_to_out(a) for a in agents]
    return SwarmOut(
        id=f"proposed-{capability}",
        name=f"Proposed swarm: {capability}",
        description=(
            "A proposed swarm of agents that can be discovered and grouped by "
            f"capability '{capability}'. Not persisted. Statuses are client-reported."
        ),
        member_agent_ids=[a.id for a in agents],
        required_capabilities=[capability],
        proposed=True,
        persisted=False,
        note="Statuses are client-reported. This registry does not probe liveness. Messaging is FUTURE.",
        members=members,
    )


@router.post(
    "/swarms",
    status_code=status.HTTP_201_CREATED,
    response_model=SwarmOut,
    tags=["swarms"],
)
def create_swarm(payload: SwarmCreate, db: Db, _: Auth) -> SwarmOut:
    if db.get(Swarm, payload.id) is not None:
        raise _http_error(409, "conflict", f"swarm id already exists: {payload.id}")
    for agent_id in payload.member_agent_ids:
        if db.get(Agent, agent_id) is None:
            raise _http_error(400, "bad_request", f"unknown member agent: {agent_id}")
    swarm = Swarm(
        id=payload.id,
        name=payload.name,
        description=payload.description,
        required_capabilities_json=json.dumps(payload.required_capabilities),
    )
    db.add(swarm)
    db.flush()
    for agent_id in payload.member_agent_ids:
        db.add(SwarmMember(swarm_id=swarm.id, agent_id=agent_id))
    db.commit()
    swarm = db.scalar(
        select(Swarm).options(selectinload(Swarm.members)).where(Swarm.id == payload.id)
    )
    assert swarm is not None
    return swarm_to_out(swarm)


@router.get("/swarms", response_model=SwarmList, tags=["swarms"])
def list_swarms(db: Db) -> SwarmList:
    swarms = list(
        db.scalars(select(Swarm).options(selectinload(Swarm.members)).order_by(Swarm.id))
    )
    items = [swarm_to_out(s) for s in swarms]
    return SwarmList(items=items, count=len(items))


@router.get("/swarms/{swarm_id}", response_model=SwarmOut, tags=["swarms"])
def get_swarm(swarm_id: str, db: Db) -> SwarmOut:
    swarm = db.scalar(
        select(Swarm).options(selectinload(Swarm.members)).where(Swarm.id == swarm_id)
    )
    if swarm is None:
        raise _http_error(404, "not_found", f"swarm not found: {swarm_id}")
    member_ids = [m.agent_id for m in swarm.members]
    agents = []
    if member_ids:
        agents = list(
            db.scalars(
                select(Agent)
                .options(selectinload(Agent.capabilities))
                .where(Agent.id.in_(member_ids))
            )
        )
    return swarm_to_out(swarm, members=[agent_to_out(a) for a in agents])


@router.post("/swarms/{swarm_id}/members", response_model=SwarmOut, tags=["swarms"])
def add_swarm_member(swarm_id: str, payload: SwarmMemberAdd, db: Db, _: Auth) -> SwarmOut:
    swarm = db.get(Swarm, swarm_id)
    if swarm is None:
        raise _http_error(404, "not_found", f"swarm not found: {swarm_id}")
    if db.get(Agent, payload.agent_id) is None:
        raise _http_error(400, "bad_request", f"unknown member agent: {payload.agent_id}")
    existing = db.scalar(
        select(SwarmMember).where(
            SwarmMember.swarm_id == swarm_id, SwarmMember.agent_id == payload.agent_id
        )
    )
    if existing is not None:
        raise _http_error(409, "conflict", "agent is already a member of this swarm")
    db.add(SwarmMember(swarm_id=swarm_id, agent_id=payload.agent_id))
    db.commit()
    return get_swarm(swarm_id, db)
