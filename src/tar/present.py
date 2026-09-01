"""HTML presentation helpers. Read-only views of existing registry data.

Does not change protocol, signatures, replay protection, or API contracts.
"""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from tar.models import Agent, AgentCapability, Contribution, Task

# Compact example copied from docs/protocol.md — protocol docs remain source of truth.
EXAMPLE_MESSAGE = {
    "message_id": "msg-...",
    "type": "REQUEST",
    "from": "test-research",
    "to": "test-document",
    "timestamp": "2026-09-01T04:00:00Z",
    "task_id": "task-...",
    "payload": {},
    "signature": "<64-byte Ed25519 hex>",
}

_AVATAR_PALETTES = (
    ("#e4c39a", "#3b2a1c", "#c4783a"),
    ("#9dbeb4", "#1c2c28", "#5e8f82"),
    ("#d4a090", "#2c1c18", "#a85c4c"),
    ("#c8b896", "#242018", "#8a7a58"),
    ("#b8c4c0", "#1a2220", "#6a8a82"),
    ("#e8c8a0", "#2a2014", "#b8864a"),
    ("#c0a8b8", "#241c22", "#8a6878"),
    ("#a8c4d0", "#182228", "#5a8494"),
)


def short_did(did: str | None, head: int = 18, tail: int = 8) -> str:
    value = (did or "").strip()
    if len(value) <= head + tail + 1:
        return value
    return f"{value[:head]}…{value[-tail:]}"


def evidence_kind(status: str | None) -> str:
    value = (status or "claimed").lower()
    if value in {"verified", "community-verified"}:
        return "verified"
    if value in {"disputed", "expired"}:
        return value
    return "claimed"


def evidence_label(status: str | None) -> str:
    kind = evidence_kind(status)
    return {
        "verified": "VERIFIED",
        "disputed": "DISPUTED",
        "expired": "EXPIRED",
        "claimed": "CLAIMED",
    }[kind]


def avatar_spec(seed: str | None) -> dict[str, Any]:
    """Deterministic abstract mark from a public DID or agent id."""
    digest = hashlib.sha256((seed or "?").encode("utf-8")).digest()
    palette = _AVATAR_PALETTES[digest[0] % len(_AVATAR_PALETTES)]
    return {
        "fg": palette[0],
        "bg": palette[1],
        "accent": palette[2],
        "motif": digest[1] % 4,
        "rot": digest[2] % 60,
        "cx": 22 + digest[3] % 20,
        "cy": 20 + digest[4] % 22,
        "r": 10 + digest[5] % 14,
    }


def _cap_ids(agent: Any) -> list[str]:
    caps = getattr(agent, "capabilities", None) or []
    out: list[str] = []
    for cap in caps:
        if hasattr(cap, "id"):
            cid = cap.id
        elif hasattr(cap, "capability_id"):
            cid = cap.capability_id
        elif isinstance(cap, dict):
            cid = cap.get("id") or cap.get("capability_id")
        else:
            cid = None
        if cid:
            out.append(str(cid))
    return out


def network_graph(agents: list[Any], *, width: int = 560, height: int = 340) -> dict[str, Any]:
    """SVG node field from real agents. Empty when the registry is quiet."""
    nodes: list[dict[str, Any]] = []
    for agent in agents:
        aid = getattr(agent, "id", "") or ""
        digest = hashlib.sha256(aid.encode("utf-8")).digest()
        pad = 28
        x = pad + (digest[0] / 255.0) * (width - pad * 2)
        y = pad + (digest[1] / 255.0) * (height - pad * 2)
        x = min(width - pad, max(pad, x + ((digest[2] % 13) - 6)))
        y = min(height - pad, max(pad, y + ((digest[3] % 13) - 6)))
        nodes.append(
            {
                "id": aid,
                "name": getattr(agent, "name", aid),
                "did": getattr(agent, "did", ""),
                "status": getattr(agent, "status", "unknown"),
                "fictional": bool(getattr(agent, "fictional", True)),
                "x": round(x, 1),
                "y": round(y, 1),
                "caps": _cap_ids(agent),
            }
        )
    edges: list[dict[str, float | str]] = []
    seen: set[tuple[str, str]] = set()
    for i, left in enumerate(nodes):
        left_caps = set(left["caps"])
        for right in nodes[i + 1 :]:
            shared = left_caps & set(right["caps"])
            if not shared:
                continue
            pair = (left["id"], right["id"])
            if pair in seen:
                continue
            seen.add(pair)
            edges.append(
                {
                    "x1": left["x"],
                    "y1": left["y"],
                    "x2": right["x"],
                    "y2": right["y"],
                    "via": next(iter(shared)),
                }
            )
            if len(edges) >= 36:
                break
        if len(edges) >= 36:
            break
    return {"width": width, "height": height, "nodes": nodes, "edges": edges}


def registry_counts(db: Session) -> dict[str, int]:
    """Local SQLite counts only. Never invent activity."""
    status_rows = db.execute(select(Agent.status, func.count()).group_by(Agent.status))
    by_status = {str(status): int(n) for status, n in status_rows}
    return {
        "agents": int(db.scalar(select(func.count()).select_from(Agent)) or 0),
        "tasks": int(db.scalar(select(func.count()).select_from(Task)) or 0),
        "contributions": int(db.scalar(select(func.count()).select_from(Contribution)) or 0),
        "capabilities": int(
            db.scalar(select(func.count(func.distinct(AgentCapability.capability_id)))) or 0
        ),
        "online": by_status.get("online", 0),
        "busy": by_status.get("busy", 0),
        "offline": by_status.get("offline", 0),
        "unknown": by_status.get("unknown", 0),
    }


def card_stats(db: Session, agent_ids: list[str]) -> dict[str, dict[str, int]]:
    """Per-agent task and contribution counts from existing tables."""
    out = {aid: {"tasks": 0, "completed": 0, "contributions": 0} for aid in agent_ids}
    if not agent_ids:
        return out
    for agent_id, n in db.execute(
        select(Contribution.agent_id, func.count())
        .where(Contribution.agent_id.in_(agent_ids))
        .group_by(Contribution.agent_id)
    ):
        if agent_id in out:
            out[agent_id]["contributions"] = int(n)
    seen_tasks: dict[str, set[str]] = {aid: set() for aid in agent_ids}
    rows = db.execute(
        select(Task.id, Task.requester_id, Task.assignee_id, Task.status).where(
            or_(Task.requester_id.in_(agent_ids), Task.assignee_id.in_(agent_ids))
        )
    )
    for task_id, requester, assignee, status in rows:
        for aid in (requester, assignee):
            if aid not in out or task_id in seen_tasks[aid]:
                continue
            seen_tasks[aid].add(task_id)
            out[aid]["tasks"] += 1
            if status in {"completed", "verified"}:
                out[aid]["completed"] += 1
    return out


def protocol_values(agents: list[Any]) -> list[str]:
    found: set[str] = set()
    for agent in agents:
        for proto in getattr(agent, "protocols", None) or []:
            found.add(str(proto))
    return sorted(found)


def recent_activity(db: Session, *, limit: int = 12) -> list[dict[str, Any]]:
    """Merge real recent tasks + contributions. Empty when the registry is quiet."""
    events: list[dict[str, Any]] = []
    for task in db.scalars(select(Task).order_by(Task.created_at.desc()).limit(limit)):
        events.append(
            {
                "kind": "task",
                "id": task.id,
                "label": task.description or task.requested_capability or task.id,
                "status": task.status,
                "href": f"/ui/tasks/{task.id}",
                "when": task.created_at,
                "meta": f"{task.requester_id} → {task.assignee_id or 'unassigned'}",
            }
        )
    for row in db.scalars(
        select(Contribution).order_by(Contribution.created_at.desc()).limit(limit)
    ):
        events.append(
            {
                "kind": "contribution",
                "id": str(row.id),
                "label": row.event,
                "status": row.verification_state,
                "href": f"/ui/contributions/{row.id}",
                "when": row.created_at,
                "meta": row.agent_id,
            }
        )
    events.sort(key=lambda e: e["when"] or 0, reverse=True)
    return events[:limit]


def registration_history(db: Session, *, limit: int = 50) -> list[dict[str, Any]]:
    """Closest real analog to deployments: agent registration timestamps."""
    rows = list(
        db.scalars(select(Agent).order_by(Agent.created_at.desc()).limit(limit))
    )
    # reload with capabilities via separate query if needed — created_at only for list
    out: list[dict[str, Any]] = []
    for agent in rows:
        out.append(
            {
                "id": agent.id,
                "name": agent.name,
                "did": agent.did,
                "status": agent.status,
                "fictional": agent.fictional.lower() != "false",
                "created_at": agent.created_at,
                "href": f"/ui/agents/{agent.id}",
            }
        )
    return out
