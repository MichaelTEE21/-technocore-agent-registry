"""REST API: agents, lookup, proof, discover, verification, tasks, messages, contributions, swarms."""

from __future__ import annotations

import json
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from tar.db import get_db
from tar.identity import IdentityError, default_identity_provider
from tar.models import (
    Agent,
    AgentCapability,
    Contribution,
    Message,
    Swarm,
    SwarmMember,
    Task,
    VerificationRecord,
    utcnow,
)
from tar.proof import build_proof_document
from tar.ranking import RANKING_DOC, rank_agents
from tar.schemas import (
    AgentCreate,
    AgentList,
    AgentOut,
    AgentUpdate,
    CapabilityOut,
    ContributionCreate,
    ContributionList,
    DiscoverOut,
    LookupOut,
    MessageCreate,
    MessageList,
    MetricsOut,
    RankedAgent,
    SwarmCreate,
    SwarmList,
    SwarmMemberAdd,
    SwarmOut,
    SwarmPropose,
    TaskAction,
    TaskCreate,
    TaskList,
    TaskOut,
    TaskResultAction,
    VerificationCreate,
    VerificationList,
)
from tar.security import error_body, require_registry_token
from tar.serialize import (
    agent_to_out,
    contribution_to_out,
    message_to_out,
    swarm_to_out,
    task_to_out,
    verification_to_out,
)
from tar.taxonomy import all_categories, get_capability, list_capabilities
from tar.workflow import (
    WorkflowError,
    accept_task,
    add_contribution,
    apply_message,
    create_task,
    dispute_task,
    fail_task,
    metrics_for,
    progress_task,
    record_verification,
    reject_task,
    signature_status_for,
    submit_result,
    verify_task,
)

router = APIRouter()
Db = Annotated[Session, Depends(get_db)]
Auth = Annotated[None, Depends(require_registry_token)]


def _http_error(code: int, slug: str, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail=error_body(slug, message)["error"])


def _wf(exc: WorkflowError) -> HTTPException:
    return _http_error(exc.http_status, exc.code, str(exc))


def _get_agent(db: Session, agent_id: str) -> Agent:
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise _http_error(404, "not_found", f"agent not found: {agent_id}")
    return agent


def _loaded_agent(db: Session, agent_id: str) -> Agent:
    agent = db.scalar(
        select(Agent).options(selectinload(Agent.capabilities)).where(Agent.id == agent_id)
    )
    if agent is None:
        raise _http_error(404, "not_found", f"agent not found: {agent_id}")
    return agent


def _public_did_or_400(raw: str | None) -> str:
    if raw is None or not str(raw).strip():
        raise _http_error(400, "bad_request", "did query parameter is required")
    try:
        return default_identity_provider.validate_public_did(raw)
    except IdentityError as exc:
        raise _http_error(400, "bad_request", str(exc)) from exc


def _agent_by_did(db: Session, did: str) -> Agent | None:
    return db.scalar(
        select(Agent).options(selectinload(Agent.capabilities)).where(Agent.did == did)
    )


def _proof_from_agent(agent: Agent) -> dict:
    out = agent_to_out(agent)
    return build_proof_document(
        did=out.did,
        found=True,
        agent_id=out.id,
        name=out.name,
        capabilities=out.capabilities,
        verification={"status": out.verification.status},
        public_key=out.public_key,
    )


def _proof_download(doc: dict, filename: str) -> JSONResponse:
    return JSONResponse(
        content=doc,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _record_profile_proof(db: Session, agent: Agent) -> None:
    add_contribution(
        db,
        agent_id=agent.id,
        event="profile_proof_generated",
        detail="Public profile proof snapshot generated. Local registry only; not a token claim.",
        verification_state=agent.verification_status,
    )


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
                evidence_status=getattr(claim, "evidence_status", None) or "claimed",
            )
        )


def _ranked(agent: Agent, meta: dict[str, Any], role: str | None = None) -> RankedAgent:
    return RankedAgent(
        agent=agent_to_out(agent),
        rank=meta["rank"],
        rank_breakdown=meta["rank_breakdown"],
        matched_capabilities=meta["matched_capabilities"],
        role=role,  # type: ignore[arg-type]
    )


@router.get("/healthz", tags=["meta"])
def healthz(request: Request) -> dict:
    version = getattr(request.app, "version", "1.0.0")
    return {"status": "ok", "version": version, "service": "technocore-agent-registry"}


@router.get("/lookup", response_model=LookupOut, tags=["lookup"])
def lookup_did(db: Db, did: str | None = Query(default=None)) -> LookupOut:
    public_did = _public_did_or_400(did)
    agent = _agent_by_did(db, public_did)
    if agent is None:
        return LookupOut(
            found=False,
            did=public_did,
            format="ok",
            agent=None,
            capabilities=[],
            message="Valid public DID, not in this local registry.",
        )
    out = agent_to_out(agent)
    return LookupOut(
        found=True,
        did=public_did,
        format="ok",
        agent=out,
        capabilities=out.capabilities,
    )


@router.get("/proof", tags=["proof"])
def proof_did(db: Db, did: str | None = Query(default=None)) -> JSONResponse:
    public_did = _public_did_or_400(did)
    agent = _agent_by_did(db, public_did)
    if agent is None:
        doc = build_proof_document(
            did=public_did,
            found=False,
            agent_id=None,
            name=None,
            capabilities=[],
            verification=None,
            public_key=None,
        )
        return _proof_download(doc, "proof-unregistered.json")
    doc = _proof_from_agent(agent)
    _record_profile_proof(db, agent)
    db.commit()
    return _proof_download(doc, f"proof-{agent.id}.json")


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
        public_key=payload.public_key,
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
            summary="Registered; capabilities are self-claimed until independently checked and vouched.",
        )
    )
    db.commit()
    db.refresh(agent)
    return agent_to_out(_loaded_agent(db, agent.id))


@router.get("/agents", response_model=AgentList, tags=["agents"])
def list_agents(
    db: Db,
    capability: str | None = Query(default=None),
    category: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    protocol: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> AgentList:
    stmt = select(Agent).options(selectinload(Agent.capabilities)).order_by(Agent.id)
    joined = False
    if capability:
        stmt = stmt.join(AgentCapability).where(AgentCapability.capability_id == capability)
        joined = True
    if category:
        if joined:
            stmt = stmt.where(AgentCapability.category == category)
        else:
            stmt = stmt.join(AgentCapability).where(AgentCapability.category == category)
            joined = True
    if status_filter:
        if status_filter not in {"online", "busy", "offline", "unknown"}:
            raise _http_error(400, "bad_request", "status must be online|busy|offline|unknown")
        stmt = stmt.where(Agent.status == status_filter)
    if protocol:
        stmt = stmt.where(Agent.protocols_json.contains(f'"{protocol}"'))
    stmt = stmt.distinct()
    agents = list(db.scalars(stmt).unique())
    total = len(agents)
    page = agents[offset : offset + limit]
    items = [agent_to_out(a) for a in page]
    return AgentList(items=items, count=len(items), total=total, limit=limit, offset=offset)


@router.get("/agents/{agent_id}", response_model=AgentOut, tags=["agents"])
def get_agent(agent_id: str, db: Db) -> AgentOut:
    return agent_to_out(_loaded_agent(db, agent_id))


@router.get("/agents/{agent_id}/proof", tags=["proof"])
def agent_proof(agent_id: str, db: Db) -> JSONResponse:
    agent = _loaded_agent(db, agent_id)
    doc = _proof_from_agent(agent)
    _record_profile_proof(db, agent)
    db.commit()
    return _proof_download(doc, f"proof-{agent.id}.json")


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
    if payload.public_key is not None:
        agent.public_key = payload.public_key
    if payload.capabilities is not None:
        _replace_capabilities(db, agent, payload.capabilities)
    agent.updated_at = utcnow()
    db.commit()
    return agent_to_out(_loaded_agent(db, agent_id))


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


@router.get("/discover", response_model=DiscoverOut, tags=["discover"])
def discover(
    db: Db,
    capability: Annotated[list[str] | None, Query()] = None,
    protocol: str | None = Query(default=None),
) -> DiscoverOut:
    requested = capability or []
    if not requested:
        raise _http_error(400, "bad_request", "at least one capability query parameter is required")
    for cap in requested:
        if get_capability(cap) is None:
            raise _http_error(404, "not_found", f"capability not found: {cap}")
    stmt = select(Agent).options(selectinload(Agent.capabilities)).order_by(Agent.id)
    agents = list(db.scalars(stmt).unique())
    # Keep agents that match at least one requested capability.
    filtered = [
        a for a in agents if {c.capability_id for c in a.capabilities} & set(requested)
    ]
    ranked = rank_agents(filtered, requested, protocol=protocol)
    items = [_ranked(a, meta) for a, meta in ranked]
    return DiscoverOut(capabilities=requested, items=items, count=len(items), ranking=RANKING_DOC)


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
    agent = _loaded_agent(db, agent_id)
    try:
        record_verification(
            db,
            agent,
            kind=payload.kind,
            summary=payload.summary,
            evidence_uri=payload.evidence_uri,
            capability_id=payload.capability_id,
            checker_id=payload.checker_id,
        )
    except WorkflowError as exc:
        raise _wf(exc) from exc
    db.commit()
    return get_verification(agent_id, db)


@router.get("/agents/{agent_id}/metrics", response_model=MetricsOut, tags=["metrics"])
def get_metrics(agent_id: str, db: Db) -> MetricsOut:
    agent = _loaded_agent(db, agent_id)
    return MetricsOut(**metrics_for(db, agent))


@router.get("/agents/{agent_id}/contributions", response_model=ContributionList, tags=["contributions"])
def get_agent_contributions(agent_id: str, db: Db) -> ContributionList:
    _get_agent(db, agent_id)
    rows = list(
        db.scalars(
            select(Contribution)
            .where(Contribution.agent_id == agent_id)
            .order_by(Contribution.created_at.desc())
        )
    )
    return ContributionList(items=[contribution_to_out(r) for r in rows], count=len(rows))


@router.get("/contributions", response_model=ContributionList, tags=["contributions"])
def list_contributions(
    db: Db,
    agent: str | None = Query(default=None),
    event: str | None = Query(default=None),
) -> ContributionList:
    stmt = select(Contribution).order_by(Contribution.created_at.desc())
    if agent:
        stmt = stmt.where(Contribution.agent_id == agent)
    if event:
        stmt = stmt.where(Contribution.event == event)
    rows = list(db.scalars(stmt))
    return ContributionList(items=[contribution_to_out(r) for r in rows], count=len(rows))


@router.post(
    "/contributions",
    status_code=status.HTTP_201_CREATED,
    response_model=ContributionList,
    tags=["contributions"],
)
def post_contribution(payload: ContributionCreate, db: Db, _: Auth) -> ContributionList:
    if payload.event not in {
        "community_endorsement",
        "dispute",
        "task_completed",
        "task_failed",
        "result_verified",
        "capability_verified",
        "profile_proof_generated",
    }:
        raise _http_error(400, "bad_request", "unknown contribution event")
    if payload.event in {
        "task_completed",
        "task_failed",
        "result_verified",
        "capability_verified",
        "profile_proof_generated",
    }:
        raise _http_error(
            400,
            "bad_request",
            "this event is recorded by the task/verification/proof workflow; POST only community_endorsement or dispute",
        )
    _get_agent(db, payload.agent_id)
    add_contribution(
        db,
        agent_id=payload.agent_id,
        event=payload.event,
        task_id=payload.task_id,
        reference=payload.reference,
        verification_state=payload.verification_state,
        detail=payload.detail,
    )
    db.commit()
    return list_contributions(db, agent=payload.agent_id, event=payload.event)


@router.post("/tasks", status_code=status.HTTP_201_CREATED, response_model=TaskOut, tags=["tasks"])
def post_task(payload: TaskCreate, db: Db, _: Auth) -> TaskOut:
    try:
        task = create_task(
            db,
            requester=payload.requester,
            requested_capability=payload.requested_capability,
            description=payload.description,
            assignee=payload.assignee,
            protocol=payload.protocol,
            task_id=payload.task_id,
        )
    except WorkflowError as exc:
        raise _wf(exc) from exc
    db.commit()
    return task_to_out(task)


@router.get("/tasks", response_model=TaskList, tags=["tasks"])
def list_tasks(
    db: Db,
    status_filter: str | None = Query(default=None, alias="status"),
    capability: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> TaskList:
    stmt = select(Task).order_by(Task.created_at.desc())
    if status_filter:
        stmt = stmt.where(Task.status == status_filter)
    if capability:
        stmt = stmt.where(Task.requested_capability == capability)
    rows = list(db.scalars(stmt))
    total = len(rows)
    page = rows[offset : offset + limit]
    items = [task_to_out(t) for t in page]
    return TaskList(items=items, count=len(items), total=total, limit=limit, offset=offset)


@router.get("/tasks/{task_id}", response_model=TaskOut, tags=["tasks"])
def get_task(task_id: str, db: Db) -> TaskOut:
    task = db.get(Task, task_id)
    if task is None:
        raise _http_error(404, "not_found", f"task not found: {task_id}")
    return task_to_out(task)


def _run_task_action(db: Session, task_id: str, fn, payload) -> TaskOut:
    task = db.get(Task, task_id)
    if task is None:
        raise _http_error(404, "not_found", f"task not found: {task_id}")
    data = payload.model_dump()
    try:
        fn(db, task, data)
    except WorkflowError as exc:
        raise _wf(exc) from exc
    db.commit()
    db.refresh(task)
    return task_to_out(task)


@router.post("/tasks/{task_id}/accept", response_model=TaskOut, tags=["tasks"])
def post_accept(task_id: str, payload: TaskAction, db: Db, _: Auth) -> TaskOut:
    return _run_task_action(db, task_id, accept_task, payload)


@router.post("/tasks/{task_id}/reject", response_model=TaskOut, tags=["tasks"])
def post_reject(task_id: str, payload: TaskAction, db: Db, _: Auth) -> TaskOut:
    return _run_task_action(db, task_id, reject_task, payload)


@router.post("/tasks/{task_id}/progress", response_model=TaskOut, tags=["tasks"])
def post_progress(task_id: str, payload: TaskAction, db: Db, _: Auth) -> TaskOut:
    return _run_task_action(db, task_id, progress_task, payload)


@router.post("/tasks/{task_id}/result", response_model=TaskOut, tags=["tasks"])
def post_result(task_id: str, payload: TaskResultAction, db: Db, _: Auth) -> TaskOut:
    return _run_task_action(db, task_id, submit_result, payload)


@router.post("/tasks/{task_id}/fail", response_model=TaskOut, tags=["tasks"])
def post_fail(task_id: str, payload: TaskAction, db: Db, _: Auth) -> TaskOut:
    return _run_task_action(db, task_id, fail_task, payload)


@router.post("/tasks/{task_id}/verify", response_model=TaskOut, tags=["tasks"])
def post_verify_task(task_id: str, payload: TaskAction, db: Db, _: Auth) -> TaskOut:
    return _run_task_action(db, task_id, verify_task, payload)


@router.post("/tasks/{task_id}/dispute", response_model=TaskOut, tags=["tasks"])
def post_dispute_task(task_id: str, payload: TaskAction, db: Db, _: Auth) -> TaskOut:
    return _run_task_action(db, task_id, dispute_task, payload)


@router.post("/messages", status_code=status.HTTP_201_CREATED, tags=["messages"])
def post_message(payload: MessageCreate, db: Db, _: Auth) -> dict:
    envelope = payload.model_dump(by_alias=True)
    try:
        row, task = apply_message(db, envelope)
    except WorkflowError as exc:
        raise _wf(exc) from exc
    db.commit()
    out: dict[str, Any] = {"message": message_to_out(row).model_dump(by_alias=True)}
    if task is not None:
        out["task"] = task_to_out(task).model_dump()
    return out


@router.get("/messages", response_model=MessageList, tags=["messages"])
def list_messages(
    db: Db,
    task_id: str | None = Query(default=None),
    type: str | None = Query(default=None),
    from_agent: str | None = Query(default=None, alias="from"),
) -> MessageList:
    stmt = select(Message).order_by(Message.created_at.asc())
    if task_id:
        stmt = stmt.where(Message.task_id == task_id)
    if type:
        stmt = stmt.where(Message.type == type)
    if from_agent:
        stmt = stmt.where(Message.from_agent == from_agent)
    rows = list(db.scalars(stmt))
    return MessageList(items=[message_to_out(r) for r in rows], count=len(rows))


@router.get("/messages/{message_id}", tags=["messages"])
def get_message(message_id: str, db: Db) -> dict:
    row = db.scalar(select(Message).where(Message.message_id == message_id))
    if row is None:
        raise _http_error(404, "not_found", f"message not found: {message_id}")
    return message_to_out(row).model_dump(by_alias=True)


@router.post("/messages/{message_id}/verify", tags=["messages"])
def post_verify_message(message_id: str, db: Db) -> dict:
    """Cryptographic envelope check. Does not change task state.

    Distinct from POST /tasks/{id}/verify (independent re-run).
    Presence of a signature is not proof. Valid signature ≠ correct answer.
    """
    row = db.scalar(select(Message).where(Message.message_id == message_id))
    if row is None:
        raise _http_error(404, "not_found", f"message not found: {message_id}")
    status_label = signature_status_for(db, row)
    return {
        "message_id": message_id,
        "signature_status": status_label,
        "valid": status_label == "VALID",
        "note": (
            "Identity check ≠ signature valid ≠ agent verification status ≠ "
            "task complete ≠ result is true. A valid signature does not mean "
            "the result is correct. Presence of a signature is not proof."
        ),
    }


def _assemble(
    db: Session,
    capabilities: list[str],
    protocol: str | None = None,
) -> tuple[list[RankedAgent], list[RankedAgent], list[str]]:
    for cap in capabilities:
        if get_capability(cap) is None:
            raise _http_error(404, "not_found", f"capability not found: {cap}")
    stmt = (
        select(Agent)
        .options(selectinload(Agent.capabilities))
        .where(Agent.status.in_(("online", "unknown")))
        .order_by(Agent.id)
    )
    agents = list(db.scalars(stmt).unique())
    wanted = set(capabilities)
    matching = [a for a in agents if {c.capability_id for c in a.capabilities} & wanted]
    ranked = rank_agents(matching, capabilities, protocol=protocol)
    recommended = [_ranked(a, meta, role="recommended") for a, meta in ranked]
    executing: list[RankedAgent] = []
    covered: set[str] = set()
    used: set[str] = set()
    for agent, meta in ranked:
        leftover = [c for c in capabilities if c in meta["matched_capabilities"] and c not in covered]
        if not leftover:
            continue
        executing.append(_ranked(agent, meta, role="executing"))
        covered.update(leftover)
        used.add(agent.id)
        if covered >= wanted:
            break
    return recommended, executing, [r.agent.id for r in executing]


@router.get("/swarms/assemble", response_model=SwarmOut, tags=["swarms"])
def assemble_swarm(
    db: Db,
    capability: Annotated[list[str] | None, Query()] = None,
    protocol: str | None = Query(default=None),
) -> SwarmOut:
    caps = capability or []
    if not caps:
        raise _http_error(400, "bad_request", "capability query parameter is required")
    recommended, executing, exec_ids = _assemble(db, caps, protocol)
    label = "+".join(caps)
    return SwarmOut(
        id=f"proposed-{label}",
        name=f"Proposed swarm: {label}",
        description=(
            "Local proposal of agents for a multi-capability task. "
            "recommended = matching candidates; executing = one covering set. "
            "Not a live network."
        ),
        member_agent_ids=exec_ids or [r.agent.id for r in recommended],
        required_capabilities=caps,
        proposed=True,
        persisted=False,
        note=(
            "Statuses are client-reported. This registry does not probe liveness. "
            "Recommended vs executing are distinct. Local only."
        ),
        members=[r.agent for r in (executing or recommended)],
        recommended=recommended,
        executing=executing,
    )


@router.post("/swarms/propose", response_model=SwarmOut, tags=["swarms"])
def propose_swarm(payload: SwarmPropose, db: Db, _: Auth) -> SwarmOut:
    recommended, executing, exec_ids = _assemble(db, payload.capabilities, payload.protocol)
    sid = payload.id or f"proposed-{uuid.uuid4().hex[:10]}"
    name = payload.name or f"Proposed swarm: {'+'.join(payload.capabilities)}"
    if payload.persist:
        if db.get(Swarm, sid) is not None:
            raise _http_error(409, "conflict", f"swarm id already exists: {sid}")
        swarm = Swarm(
            id=sid,
            name=name,
            description="Persisted local swarm proposal. Not a live executing network.",
            required_capabilities_json=json.dumps(payload.capabilities),
        )
        db.add(swarm)
        db.flush()
        for item in recommended:
            role = "executing" if item.agent.id in exec_ids else "recommended"
            db.add(SwarmMember(swarm_id=sid, agent_id=item.agent.id, role=role))
        db.commit()
        return get_swarm(sid, db)
    return SwarmOut(
        id=sid,
        name=name,
        description="Local proposal of agents for a multi-capability task. Not persisted.",
        member_agent_ids=exec_ids,
        required_capabilities=payload.capabilities,
        proposed=True,
        persisted=False,
        note="Recommended vs executing are distinct. Local only. Not a live network.",
        members=[r.agent for r in executing],
        recommended=recommended,
        executing=executing,
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
        db.add(SwarmMember(swarm_id=swarm.id, agent_id=agent_id, role="executing"))
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
    by_id = {a.id: a for a in agents}
    recommended = []
    executing = []
    dummy_meta = {
        "rank": 0.0,
        "rank_breakdown": {
            "capability_match": 0,
            "verification_status": 0,
            "availability": 0,
            "compatibility": 0,
            "evidence": 0,
        },
        "matched_capabilities": [],
    }
    for member in swarm.members:
        agent = by_id.get(member.agent_id)
        if agent is None:
            continue
        ranked = _ranked(agent, dummy_meta, role=member.role)
        if member.role == "executing":
            executing.append(ranked)
        else:
            recommended.append(ranked)
    return swarm_to_out(
        swarm,
        members=[agent_to_out(a) for a in agents],
        recommended=recommended or None,
        executing=executing or None,
    )


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
    db.add(SwarmMember(swarm_id=swarm_id, agent_id=payload.agent_id, role=payload.role))
    db.commit()
    return get_swarm(swarm_id, db)
