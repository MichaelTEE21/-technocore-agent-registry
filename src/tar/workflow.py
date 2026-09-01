"""Task state machine, signed messages, contributions. Local registry only."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from tar.crypto import (
    SignatureError,
    canonical_message_bytes,
    resolve_verify_key,
    verify_or_raise,
)
from tar.models import (
    Agent,
    Contribution,
    Message,
    ReputationEvent,
    Task,
    TaskEvent,
    VerificationRecord,
    utcnow,
)

TASK_TRANSITIONS: dict[str, set[str]] = {
    "requested": {"accepted", "rejected"},
    "accepted": {"in_progress", "rejected", "failed"},
    "rejected": set(),
    "in_progress": {"completed", "failed"},
    "completed": {"verified", "disputed"},
    "failed": {"disputed"},
    "verified": {"disputed"},
    "disputed": set(),
}

REPLAY_MAX_AGE = timedelta(hours=24)
REPLAY_FUTURE_SKEW = timedelta(minutes=5)

MESSAGE_TYPES = {"REQUEST", "ACCEPT", "REJECT", "PROGRESS", "RESULT", "VERIFY"}


class WorkflowError(ValueError):
    def __init__(self, code: str, message: str, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


def _iso(now: datetime | None = None) -> str:
    stamp = now or datetime.now(UTC)
    return stamp.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise WorkflowError("validation_error", f"invalid timestamp: {value}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def new_id(prefix: str = "t") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def transition(task: Task, new_status: str) -> None:
    allowed = TASK_TRANSITIONS.get(task.status, set())
    if new_status not in allowed:
        raise WorkflowError(
            "conflict",
            f"invalid task transition {task.status} -> {new_status}",
            http_status=409,
        )
    task.status = new_status
    task.updated_at = utcnow()


def add_event(db: Session, task: Task, event: str, actor_id: str | None, detail: str = "") -> None:
    db.add(TaskEvent(task_id=task.id, event=event, actor_id=actor_id, detail=detail[:2000]))


def add_contribution(
    db: Session,
    *,
    agent_id: str,
    event: str,
    task_id: str | None = None,
    reference: str | None = None,
    verification_state: str = "claimed",
    detail: str = "",
) -> Contribution:
    row = Contribution(
        agent_id=agent_id,
        event=event,
        task_id=task_id,
        reference=reference,
        verification_state=verification_state,
        detail=detail[:2000],
    )
    db.add(row)
    db.add(
        ReputationEvent(
            agent_id=agent_id,
            event_type=event,
            detail=(detail or event)[:500],
        )
    )
    return row


def _get_agent(db: Session, agent_id: str) -> Agent:
    agent = db.scalar(
        select(Agent).options(selectinload(Agent.capabilities)).where(Agent.id == agent_id)
    )
    if agent is None:
        raise WorkflowError("not_found", f"agent not found: {agent_id}", http_status=404)
    return agent


def check_replay(db: Session, message_id: str, timestamp: str) -> datetime:
    existing = db.scalar(select(Message).where(Message.message_id == message_id))
    if existing is not None:
        raise WorkflowError("conflict", f"duplicate message_id: {message_id}", http_status=409)
    ts = parse_timestamp(timestamp)
    now = datetime.now(UTC)
    if ts > now + REPLAY_FUTURE_SKEW:
        raise WorkflowError("validation_error", "message timestamp is in the future")
    if ts < now - REPLAY_MAX_AGE:
        raise WorkflowError("validation_error", "message timestamp is too old (replay window)")
    return ts


def require_signature(agent: Agent, fields: dict[str, Any], signature: str | None) -> None:
    key = resolve_verify_key(agent.did, agent.public_key)
    if key is None:
        return
    if not signature:
        raise WorkflowError("unauthorized", "signature required for agents with a public_key", 401)
    message = canonical_message_bytes(
        message_id=fields["message_id"],
        type=fields["type"],
        from_agent=fields["from"],
        to_agent=fields["to"],
        timestamp=fields["timestamp"],
        task_id=fields.get("task_id"),
        payload=fields.get("payload") or {},
    )
    try:
        verify_or_raise(key, message, signature)
    except SignatureError as exc:
        raise WorkflowError("unauthorized", "invalid Ed25519 signature", 401) from exc


def store_message(
    db: Session,
    *,
    message_id: str,
    type: str,
    from_agent: str,
    to_agent: str,
    timestamp: str,
    task_id: str | None,
    payload: dict[str, Any],
    signature: str | None,
    check_sig: bool = True,
) -> Message:
    if type not in MESSAGE_TYPES:
        raise WorkflowError("validation_error", f"unknown message type: {type}")
    check_replay(db, message_id, timestamp)
    sender = _get_agent(db, from_agent)
    _get_agent(db, to_agent)
    fields = {
        "message_id": message_id,
        "type": type,
        "from": from_agent,
        "to": to_agent,
        "timestamp": timestamp,
        "task_id": task_id,
        "payload": payload or {},
    }
    if check_sig:
        require_signature(sender, fields, signature)
    row = Message(
        message_id=message_id,
        type=type,
        from_agent=from_agent,
        to_agent=to_agent,
        timestamp=timestamp,
        task_id=task_id,
        payload_json=json.dumps(payload or {}),
        signature=signature,
    )
    db.add(row)
    return row


def create_task(
    db: Session,
    *,
    requester: str,
    requested_capability: str,
    description: str,
    assignee: str | None = None,
    protocol: str = "http",
    task_id: str | None = None,
    emit_request_message: bool = True,
) -> Task:
    req = _get_agent(db, requester)
    if assignee:
        worker = _get_agent(db, assignee)
        ids = {c.capability_id for c in worker.capabilities}
        if requested_capability not in ids:
            raise WorkflowError(
                "bad_request",
                f"assignee {assignee} does not advertise {requested_capability}",
            )
    tid = task_id or new_id("task")
    if db.get(Task, tid) is not None:
        raise WorkflowError("conflict", f"task id already exists: {tid}", 409)
    task = Task(
        id=tid,
        requester_id=req.id,
        assignee_id=assignee,
        requested_capability=requested_capability,
        description=description,
        status="requested",
        protocol=protocol,
    )
    db.add(task)
    db.flush()
    add_event(db, task, "created", requester, description[:500])
    if assignee and emit_request_message:
        store_message(
            db,
            message_id=new_id("msg"),
            type="REQUEST",
            from_agent=requester,
            to_agent=assignee,
            timestamp=_iso(),
            task_id=tid,
            payload={"requested_capability": requested_capability, "description": description},
            signature=None,
            check_sig=False,
        )
    return task


def _ensure_assignee(task: Task, agent_id: str) -> None:
    if task.assignee_id and task.assignee_id != agent_id:
        raise WorkflowError("forbidden", "only the assignee may perform this action", 403)
    if task.assignee_id is None:
        task.assignee_id = agent_id


def accept_task(db: Session, task: Task, action: dict[str, Any]) -> Task:
    agent_id = action["agent_id"]
    _ensure_assignee(task, agent_id)
    worker = _get_agent(db, agent_id)
    ids = {c.capability_id for c in worker.capabilities}
    if task.requested_capability not in ids:
        raise WorkflowError(
            "bad_request",
            f"agent {agent_id} does not advertise {task.requested_capability}",
        )
    _action_message(db, task, action, "ACCEPT", from_agent=agent_id, to_agent=task.requester_id)
    transition(task, "accepted")
    add_event(db, task, "accepted", agent_id)
    return task


def reject_task(db: Session, task: Task, action: dict[str, Any]) -> Task:
    agent_id = action["agent_id"]
    if agent_id not in {task.requester_id, task.assignee_id}:
        if task.assignee_id is None:
            _ensure_assignee(task, agent_id)
        else:
            raise WorkflowError("forbidden", "only requester or assignee may reject", 403)
    to_agent = task.requester_id if agent_id != task.requester_id else (task.assignee_id or task.requester_id)
    _action_message(db, task, action, "REJECT", from_agent=agent_id, to_agent=to_agent)
    transition(task, "rejected")
    add_event(db, task, "rejected", agent_id)
    return task


def progress_task(db: Session, task: Task, action: dict[str, Any]) -> Task:
    agent_id = action["agent_id"]
    if task.assignee_id != agent_id:
        raise WorkflowError("forbidden", "only the assignee may report progress", 403)
    if task.status == "accepted":
        transition(task, "in_progress")
    elif task.status != "in_progress":
        raise WorkflowError("conflict", f"cannot progress from {task.status}", 409)
    _action_message(db, task, action, "PROGRESS", from_agent=agent_id, to_agent=task.requester_id)
    add_event(db, task, "progress", agent_id, json.dumps(action.get("payload") or {})[:500])
    return task


def submit_result(db: Session, task: Task, action: dict[str, Any]) -> Task:
    agent_id = action["agent_id"]
    if task.assignee_id != agent_id:
        raise WorkflowError("forbidden", "only the assignee may submit a result", 403)
    if task.status == "accepted":
        transition(task, "in_progress")
    result = action.get("result")
    payload = action.get("payload") or {}
    if result is not None:
        payload = {**payload, "result": result}
    _action_message(db, task, action, "RESULT", from_agent=agent_id, to_agent=task.requester_id, payload=payload)
    transition(task, "completed")
    task.result_json = json.dumps(payload.get("result", payload))
    add_event(db, task, "result", agent_id)
    add_contribution(
        db,
        agent_id=agent_id,
        event="task_completed",
        task_id=task.id,
        reference=action.get("message_id"),
        verification_state="claimed",
        detail="Result submitted; cryptographic signature checked if a public_key is on file.",
    )
    return task


def fail_task(db: Session, task: Task, action: dict[str, Any]) -> Task:
    agent_id = action["agent_id"]
    if agent_id not in {task.assignee_id, task.requester_id}:
        raise WorkflowError("forbidden", "only requester or assignee may fail a task", 403)
    transition(task, "failed")
    add_event(db, task, "failed", agent_id)
    add_contribution(
        db,
        agent_id=task.assignee_id or agent_id,
        event="task_failed",
        task_id=task.id,
        verification_state="claimed",
        detail=str((action.get("payload") or {}).get("reason", "failed"))[:500],
    )
    return task


def verify_task(db: Session, task: Task, action: dict[str, Any]) -> Task:
    """Independent re-run / vouch. Checker must not be the assignee."""
    agent_id = action["agent_id"]
    if agent_id == task.assignee_id:
        raise WorkflowError(
            "forbidden",
            "independent re-run required: the assignee cannot vouch their own result",
            403,
        )
    _get_agent(db, agent_id)
    if task.status != "completed":
        raise WorkflowError("conflict", f"cannot verify from {task.status}", 409)
    payload = action.get("payload") or {}
    payload.setdefault("independent_rerun", True)
    _action_message(db, task, action, "VERIFY", from_agent=agent_id, to_agent=task.requester_id, payload=payload)
    transition(task, "verified")
    add_event(db, task, "verified", agent_id, "independent re-run before vouch")
    if task.assignee_id:
        add_contribution(
            db,
            agent_id=task.assignee_id,
            event="result_verified",
            task_id=task.id,
            reference=action.get("message_id"),
            verification_state="vouched",
            detail=f"Vouched by {agent_id} after independent re-run.",
        )
    return task


def dispute_task(db: Session, task: Task, action: dict[str, Any]) -> Task:
    agent_id = action["agent_id"]
    _get_agent(db, agent_id)
    transition(task, "disputed")
    add_event(db, task, "disputed", agent_id)
    add_contribution(
        db,
        agent_id=task.assignee_id or agent_id,
        event="dispute",
        task_id=task.id,
        verification_state="disputed",
        detail=str((action.get("payload") or {}).get("reason", "disputed"))[:500],
    )
    return task


def _action_message(
    db: Session,
    task: Task,
    action: dict[str, Any],
    type: str,
    *,
    from_agent: str,
    to_agent: str,
    payload: dict[str, Any] | None = None,
) -> Message | None:
    if action.get("_skip_message"):
        return None
    message_id = action.get("message_id") or new_id("msg")
    timestamp = action.get("timestamp") or _iso()
    body = payload if payload is not None else (action.get("payload") or {})
    signature = action.get("signature")
    check = bool(signature) or bool(_get_agent(db, from_agent).public_key)
    return store_message(
        db,
        message_id=message_id,
        type=type,
        from_agent=from_agent,
        to_agent=to_agent,
        timestamp=timestamp,
        task_id=task.id,
        payload=body,
        signature=signature,
        check_sig=check,
    )


def apply_message(db: Session, envelope: dict[str, Any]) -> tuple[Message, Task | None]:
    """Store a signed A2A message and apply it to the linked task."""
    msg_type = envelope["type"]
    from_agent = envelope.get("from") or envelope.get("from_agent")
    to_agent = envelope.get("to") or envelope.get("to_agent")
    payload = envelope.get("payload") or {}
    row = store_message(
        db,
        message_id=envelope["message_id"],
        type=msg_type,
        from_agent=from_agent,
        to_agent=to_agent,
        timestamp=envelope["timestamp"],
        task_id=envelope.get("task_id"),
        payload=payload,
        signature=envelope.get("signature"),
        check_sig=True,
    )
    task = None
    if envelope.get("task_id"):
        task = db.get(Task, envelope["task_id"])
    action = {
        "agent_id": from_agent,
        "message_id": envelope["message_id"],
        "timestamp": envelope["timestamp"],
        "signature": None,
        "payload": payload,
        "result": payload.get("result"),
        "_skip_message": True,
    }
    if task is None and msg_type == "REQUEST":
        task = create_task(
            db,
            requester=from_agent,
            requested_capability=payload.get("requested_capability") or payload.get("capability") or "web-research",
            description=str(payload.get("description") or ""),
            assignee=to_agent,
            protocol=str(payload.get("protocol") or "http"),
            task_id=envelope.get("task_id"),
            emit_request_message=False,
        )
        return row, task
    if task is None:
        return row, None
    if msg_type == "ACCEPT":
        accept_task(db, task, {**action, "signature": None})
    elif msg_type == "REJECT":
        reject_task(db, task, {**action, "signature": None})
    elif msg_type == "PROGRESS":
        progress_task(db, task, {**action, "signature": None})
    elif msg_type == "RESULT":
        submit_result(db, task, {**action, "signature": None})
    elif msg_type == "VERIFY":
        verify_task(db, task, {**action, "signature": None})
    return row, task


def record_verification(
    db: Session,
    agent: Agent,
    *,
    kind: str,
    summary: str,
    evidence_uri: str | None,
    capability_id: str | None,
    checker_id: str | None,
) -> None:
    """Credence: claim/evidence stay claimed; independent check then vouch. Never auto-verify."""
    if kind == "dispute":
        stored = "disputed"
        agent.verification_status = "disputed"
        add_contribution(
            db,
            agent_id=agent.id,
            event="dispute",
            verification_state="disputed",
            detail=summary,
        )
    elif kind == "independently-checked":
        stored = "independently-checked"
        if agent.verification_status not in {"disputed", "expired"}:
            agent.verification_status = "independently-checked"
    elif kind == "vouch":
        kinds = [
            r.kind
            for r in db.scalars(
                select(VerificationRecord).where(VerificationRecord.agent_id == agent.id)
            )
        ]
        if "independently-checked" not in kinds:
            raise WorkflowError(
                "conflict",
                "vouch requires a prior independently-checked record (independent re-run)",
                409,
            )
        if checker_id and checker_id == agent.id:
            raise WorkflowError("forbidden", "an agent cannot vouch their own claim", 403)
        stored = "vouched"
        agent.verification_status = "vouched"
        add_contribution(
            db,
            agent_id=agent.id,
            event="capability_verified",
            reference=capability_id,
            verification_state="vouched",
            detail=summary or f"Vouched by {checker_id or 'community'} after independent re-run.",
        )
    else:
        stored = "claimed"
        if agent.verification_status not in {"disputed", "expired", "vouched", "independently-checked"}:
            agent.verification_status = "claimed"

    if capability_id:
        cap = next((c for c in agent.capabilities if c.capability_id == capability_id), None)
        if cap is None:
            raise WorkflowError("not_found", f"capability not claimed: {capability_id}", 404)
        if kind == "dispute":
            cap.evidence_status = "disputed"
        elif kind == "vouch":
            cap.evidence_status = "community-verified"
        elif kind == "independently-checked":
            # still not auto-verified
            pass
        elif kind == "evidence":
            cap.evidence_status = "claimed"

    db.add(
        VerificationRecord(
            agent_id=agent.id,
            kind=kind if kind != "vouch" else "vouch",
            status=stored,
            summary=summary,
            evidence_uri=evidence_uri,
            capability_id=capability_id,
            checker_id=checker_id,
        )
    )


def metrics_for(db: Session, agent: Agent) -> dict[str, Any]:
    contribs = list(db.scalars(select(Contribution).where(Contribution.agent_id == agent.id)))
    completed = sum(1 for c in contribs if c.event == "task_completed")
    failed = sum(1 for c in contribs if c.event == "task_failed")
    verified = sum(1 for c in contribs if c.event == "result_verified")
    rate = (verified / completed) if completed else 0.0
    claimed = len(agent.capabilities)
    cap_verified = sum(
        1
        for c in agent.capabilities
        if c.evidence_status in {"verified", "community-verified"}
    )
    return {
        "agent_id": agent.id,
        "tasks_completed": completed,
        "tasks_failed": failed,
        "results_verified": verified,
        "verification_rate": round(rate, 4),
        "capabilities_claimed": claimed,
        "capabilities_verified": cap_verified,
        "contributions_recorded": len(contribs),
    }
