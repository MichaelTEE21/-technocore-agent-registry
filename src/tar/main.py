"""ASGI app: REST API + HTML demo of a swarm of agents grouped by capability."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from starlette.exceptions import HTTPException as StarletteHTTPException

from tar import __version__
from tar.api import router
from tar.config import load_settings
from tar.db import get_session_factory, init_db
from tar.models import Agent, AgentCapability, Contribution, Message, Swarm, Task, TaskEvent
from tar.present import (
    EXAMPLE_MESSAGE,
    avatar_spec,
    card_stats,
    evidence_kind,
    evidence_label,
    network_graph,
    protocol_values,
    recent_activity,
    registration_history,
    registry_counts,
    short_did,
)
from tar.ranking import RANKING_DOC, rank_agents
from tar.security import RequestLimitMiddleware, error_body
from tar.serialize import (
    agent_to_out,
    contribution_to_out,
    message_to_out,
    swarm_to_out,
    task_to_out,
)
from tar.taxonomy import all_categories, get_capability, list_capabilities
from tar.tclk_api import router as tclk_router
from tar.workflow import (
    WorkflowError,
    accept_task,
    create_task,
    reject_task,
    signature_status_for,
    submit_result,
)

PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parent.parent
SCHEMA_DIR = REPO / "docs" / "protocol"
TEMPLATES = Jinja2Templates(directory=str(PACKAGE / "templates"))
STATIC = PACKAGE / "static"
TEMPLATES.env.filters["short_did"] = short_did
TEMPLATES.env.filters["evidence_kind"] = evidence_kind
TEMPLATES.env.filters["evidence_label"] = evidence_label
TEMPLATES.env.globals["avatar_spec"] = avatar_spec

_SCHEMA_FILES = {
    "message.schema.json",
    "task.schema.json",
    "error.schema.json",
    "protocol.json",
}
_STATUS_OPTIONS = ["online", "busy", "offline", "unknown"]
_VERIFICATION_OPTIONS = [
    "claimed",
    "independently-checked",
    "vouched",
    "verified",
    "community-verified",
    "expired",
    "disputed",
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(
        title="Technocore Agent Registry",
        description=(
            "Open-source reference implementation and proposal for agent capability "
            "discovery and collaboration within the Technocore ecosystem. "
            "Local registry only — not an official Technocore component, not a live "
            "decentralized network."
        ),
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.version = __version__
    app.state.settings = settings

    app.add_middleware(
        RequestLimitMiddleware,
        max_bytes=settings.max_request_bytes,
        per_minute=settings.rate_limit_per_minute,
    )
    app.include_router(router)
    app.include_router(tclk_router)

    if STATIC.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

    @app.exception_handler(StarletteHTTPException)
    async def http_exc(_, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            body = {"error": detail}
        elif isinstance(detail, dict) and "error" in detail:
            body = detail
        else:
            body = error_body("http_error", str(detail))
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(RequestValidationError)
    async def valid_exc(_, exc: RequestValidationError):
        msg = "; ".join(
            f"{'.'.join(str(x) for x in err.get('loc', ()))}: {err.get('msg')}"
            for err in exc.errors()[:8]
        )
        return JSONResponse(status_code=422, content=error_body("validation_error", msg))

    def _agents(db, q: str | None = None, capability: str | None = None):
        agents = list(
            db.scalars(select(Agent).options(selectinload(Agent.capabilities)).order_by(Agent.id))
        )
        if capability:
            agents = [a for a in agents if any(c.capability_id == capability for c in a.capabilities)]
        if q:
            ql = q.lower()
            agents = [
                a
                for a in agents
                if ql in a.name.lower()
                or ql in a.id.lower()
                or ql in (a.did or "").lower()
                or any(ql in c.capability_id.lower() for c in a.capabilities)
            ]
        return [agent_to_out(a) for a in agents]

    def _filter_public(agents, *, protocol="", status="", verification="", name_q="", did_q=""):
        out = agents
        if protocol:
            out = [a for a in out if protocol in (a.protocols or [])]
        if status:
            out = [a for a in out if a.status == status]
        if verification:
            out = [a for a in out if a.verification.status == verification]
        if name_q:
            ql = name_q.lower()
            out = [a for a in out if ql in a.name.lower() or ql in a.id.lower()]
        if did_q:
            ql = did_q.lower()
            out = [a for a in out if ql in (a.did or "").lower()]
        return out

    @app.get("/", include_in_schema=False)
    def home(request: Request):
        db = get_session_factory()()
        try:
            q = request.query_params.get("q") or ""
            cap = request.query_params.get("capability") or ""
            listed = _agents(db, q or None, cap or None)
            all_agents = _agents(db)
            return TEMPLATES.TemplateResponse(
                request,
                "index.html",
                {
                    "agents": listed,
                    "query": q,
                    "capability": cap,
                    "version": __version__,
                    "graph": network_graph(all_agents),
                    "counts": registry_counts(db),
                    "stats": card_stats(db, [a.id for a in listed]),
                    "activity": recent_activity(db),
                    "registrations": registration_history(db, limit=12),
                },
            )
        finally:
            db.close()

    @app.get("/ui/lookup", include_in_schema=False)
    def lookup_page(request: Request):
        from urllib.parse import quote

        from tar.identity import IdentityError, default_identity_provider, looks_like_key_material
        from tar.workflow import metrics_for

        raw = request.query_params.get("did") or ""
        db = get_session_factory()()
        try:
            if not raw.strip():
                return TEMPLATES.TemplateResponse(
                    request,
                    "lookup.html",
                    {
                        "error": None,
                        "did": "",
                        "found": False,
                        "format_ok": False,
                        "agent": None,
                        "capabilities": [],
                        "metrics": None,
                        "proof_href": None,
                        "message": None,
                        "version": __version__,
                    },
                )
            display_did = "" if looks_like_key_material(raw) else raw.strip()
            try:
                did = default_identity_provider.validate_public_did(raw)
            except IdentityError as exc:
                return TEMPLATES.TemplateResponse(
                    request,
                    "lookup.html",
                    {
                        "error": str(exc),
                        "did": display_did,
                        "found": False,
                        "format_ok": False,
                        "agent": None,
                        "capabilities": [],
                        "metrics": None,
                        "proof_href": None,
                        "message": None,
                        "version": __version__,
                    },
                    status_code=400,
                )
            agent_row = db.scalar(
                select(Agent).options(selectinload(Agent.capabilities)).where(Agent.did == did)
            )
            proof_href = f"/proof?did={quote(did, safe='')}"
            if agent_row is None:
                return TEMPLATES.TemplateResponse(
                    request,
                    "lookup.html",
                    {
                        "error": None,
                        "did": did,
                        "found": False,
                        "format_ok": True,
                        "agent": None,
                        "capabilities": [],
                        "metrics": None,
                        "proof_href": proof_href,
                        "message": "Valid public DID, not in this local registry.",
                        "version": __version__,
                    },
                )
            agent = agent_to_out(agent_row)
            return TEMPLATES.TemplateResponse(
                request,
                "lookup.html",
                {
                    "error": None,
                    "did": did,
                    "found": True,
                    "format_ok": True,
                    "agent": agent,
                    "capabilities": agent.capabilities,
                    "metrics": metrics_for(db, agent_row),
                    "proof_href": proof_href,
                    "message": None,
                    "version": __version__,
                },
            )
        finally:
            db.close()

    @app.get("/ui/agents", include_in_schema=False)
    def agents_directory(request: Request):
        db = get_session_factory()()
        try:
            q = request.query_params.get("q") or ""
            cap = request.query_params.get("capability") or ""
            listed = _agents(db, q or None, cap or None)
            return TEMPLATES.TemplateResponse(
                request,
                "agents.html",
                {
                    "agents": listed,
                    "query": q,
                    "capability": cap,
                    "stats": card_stats(db, [a.id for a in listed]),
                    "version": __version__,
                },
            )
        finally:
            db.close()

    @app.get("/ui/projects", include_in_schema=False)
    def projects_alias(request: Request):
        return agents_directory(request)

    @app.get("/ui/deployments", include_in_schema=False)
    def deployments_page(request: Request):
        db = get_session_factory()()
        try:
            return TEMPLATES.TemplateResponse(
                request,
                "deployments.html",
                {
                    "registrations": registration_history(db),
                    "version": __version__,
                },
            )
        finally:
            db.close()

    @app.get("/ui/settings", include_in_schema=False)
    def settings_page(request: Request):
        return TEMPLATES.TemplateResponse(
            request,
            "settings.html",
            {"version": __version__},
        )

    @app.get("/ui/agents/new", include_in_schema=False)
    def new_agent_page(request: Request):
        return TEMPLATES.TemplateResponse(
            request,
            "agent_new.html",
            {
                "categories": all_categories(),
                "status_options": _STATUS_OPTIONS,
                "form": {},
                "error": None,
                "version": __version__,
            },
        )

    @app.post("/ui/agents/new", include_in_schema=False)
    async def new_agent_submit(request: Request):
        from fastapi.responses import RedirectResponse
        from pydantic import ValidationError
        from starlette.exceptions import HTTPException as StarletteHTTPException

        from tar.api import register_agent
        from tar.schemas import AgentCreate, CapabilityClaim
        from tar.taxonomy import CAPABILITY_INDEX

        form = await request.form()
        name = str(form.get("name") or "").strip()
        agent_id = str(form.get("id") or "").strip()
        did = str(form.get("did") or "").strip()
        description = str(form.get("description") or "").strip()
        endpoint_raw = str(form.get("endpoint") or "").strip()
        endpoint = endpoint_raw or None
        public_key_raw = str(form.get("public_key") or "").strip()
        public_key = public_key_raw or None
        status_v = str(form.get("status") or "unknown").strip() or "unknown"
        fictional = "fictional" in form
        caps_raw = form.getlist("capability") if hasattr(form, "getlist") else []
        claims = []
        for cid in caps_raw:
            cid = str(cid).strip()
            if not cid or cid not in CAPABILITY_INDEX:
                continue
            claims.append(
                {
                    "id": cid,
                    "category": CAPABILITY_INDEX[cid]["category"],
                    "level": "intermediate",
                    "evidence_status": "claimed",
                }
            )
        form_state = {
            "name": name,
            "id": agent_id,
            "did": did,
            "description": description,
            "endpoint": endpoint_raw,
            "public_key": public_key_raw,
            "status": status_v,
            "fictional": fictional,
            "caps": [c["id"] for c in claims],
        }

        def _err(msg: str, code: int = 400):
            return TEMPLATES.TemplateResponse(
                request,
                "agent_new.html",
                {
                    "categories": all_categories(),
                    "status_options": _STATUS_OPTIONS,
                    "form": form_state,
                    "error": msg,
                    "version": __version__,
                },
                status_code=code,
            )

        try:
            payload = AgentCreate(
                id=agent_id,
                name=name,
                did=did,
                description=description,
                endpoint=endpoint,
                public_key=public_key,
                status=status_v,  # type: ignore[arg-type]
                fictional=fictional,
                capabilities=[CapabilityClaim(**c) for c in claims],
                protocols=["http"],
            )
        except ValidationError as exc:
            msg = "; ".join(
                f"{'.'.join(str(x) for x in err.get('loc', ()))}: {err.get('msg')}"
                for err in exc.errors()[:6]
            )
            return _err(msg)

        db = get_session_factory()()
        try:
            try:
                out = register_agent(payload, db, None)
            except StarletteHTTPException as exc:
                detail = exc.detail
                if isinstance(detail, dict):
                    err = detail.get("error") if isinstance(detail.get("error"), dict) else detail
                    if isinstance(err, dict):
                        msg = str(err.get("message") or err)
                    else:
                        msg = str(detail)
                else:
                    msg = str(detail)
                return _err(msg, exc.status_code)
            return RedirectResponse(url=f"/ui/agents/{out.id}", status_code=303)
        finally:
            db.close()

    @app.get("/ui/agents/{agent_id}", include_in_schema=False)
    def agent_page(request: Request, agent_id: str):
        db = get_session_factory()()
        try:
            agent = db.scalar(
                select(Agent).options(selectinload(Agent.capabilities)).where(Agent.id == agent_id)
            )
            if agent is None:
                return TEMPLATES.TemplateResponse(
                    request,
                    "missing.html",
                    {"message": f"Agent {agent_id} not found", "version": __version__},
                    status_code=404,
                )
            from tar.workflow import metrics_for

            contribs = list(
                db.scalars(
                    select(Contribution)
                    .where(Contribution.agent_id == agent_id)
                    .order_by(Contribution.created_at.desc())
                )
            )
            task_rows = list(
                db.scalars(
                    select(Task)
                    .where(or_(Task.requester_id == agent_id, Task.assignee_id == agent_id))
                    .order_by(Task.created_at.desc())
                )
            )
            tab = (request.query_params.get("tab") or "overview").lower()
            if tab not in {"overview", "activity", "tasks", "proofs", "capabilities", "settings"}:
                tab = "overview"
            return TEMPLATES.TemplateResponse(
                request,
                "agent.html",
                {
                    "agent": agent_to_out(agent),
                    "metrics": metrics_for(db, agent),
                    "contributions": [contribution_to_out(c) for c in contribs[:20]],
                    "tasks": [task_to_out(t) for t in task_rows[:20]],
                    "tab": tab,
                    "version": __version__,
                },
            )
        finally:
            db.close()

    @app.get("/ui/capabilities", include_in_schema=False)
    def capabilities_page(request: Request):
        db = get_session_factory()()
        try:
            rows = db.execute(
                select(AgentCapability.capability_id, func.count()).group_by(AgentCapability.capability_id)
            )
            cap_counts = {cid: int(n) for cid, n in rows}
            return TEMPLATES.TemplateResponse(
                request,
                "capabilities.html",
                {
                    "categories": all_categories(),
                    "items": list_capabilities(),
                    "cap_counts": cap_counts,
                    "version": __version__,
                },
            )
        finally:
            db.close()

    @app.get("/ui/capabilities/{cap_id}", include_in_schema=False)
    def capability_page(request: Request, cap_id: str):
        item = get_capability(cap_id)
        if item is None:
            return TEMPLATES.TemplateResponse(
                request,
                "missing.html",
                {"message": f"Capability {cap_id} not found", "version": __version__},
                status_code=404,
            )
        db = get_session_factory()()
        try:
            rows = list(
                db.scalars(select(Agent).options(selectinload(Agent.capabilities)).order_by(Agent.id))
            )
            advertisers = []
            for agent in rows:
                claim = next((c for c in agent.capabilities if c.capability_id == cap_id), None)
                if claim is None:
                    continue
                advertisers.append(
                    {
                        "agent": agent_to_out(agent),
                        "level": claim.level,
                        "evidence": claim.evidence_status,
                        "kind": evidence_kind(claim.evidence_status),
                        "label": evidence_label(claim.evidence_status),
                    }
                )
            return TEMPLATES.TemplateResponse(
                request,
                "capability.html",
                {
                    "item": item,
                    "agents": advertisers,
                    "version": __version__,
                },
            )
        finally:
            db.close()

    @app.get("/ui/swarms", include_in_schema=False)
    def swarms_page(request: Request):
        db = get_session_factory()()
        try:
            swarms = list(
                db.scalars(select(Swarm).options(selectinload(Swarm.members)).order_by(Swarm.id))
            )
            items = []
            for swarm in swarms:
                ids = [m.agent_id for m in swarm.members]
                members = []
                if ids:
                    members = list(
                        db.scalars(
                            select(Agent)
                            .options(selectinload(Agent.capabilities))
                            .where(Agent.id.in_(ids))
                        )
                    )
                items.append(swarm_to_out(swarm, members=[agent_to_out(a) for a in members]))
            return TEMPLATES.TemplateResponse(
                request,
                "swarms.html",
                {"swarms": items, "version": __version__},
            )
        finally:
            db.close()

    @app.get("/ui/tasks", include_in_schema=False)
    def tasks_page(request: Request):
        db = get_session_factory()()
        try:
            tasks = list(db.scalars(select(Task).order_by(Task.created_at.desc())))
            return TEMPLATES.TemplateResponse(
                request,
                "tasks.html",
                {"tasks": [task_to_out(t) for t in tasks], "version": __version__},
            )
        finally:
            db.close()

    @app.get("/ui/tasks/{task_id}", include_in_schema=False)
    def task_page(request: Request, task_id: str):
        db = get_session_factory()()
        try:
            task = db.get(Task, task_id)
            if task is None:
                return TEMPLATES.TemplateResponse(
                    request,
                    "missing.html",
                    {"message": f"Task {task_id} not found", "version": __version__},
                    status_code=404,
                )
            messages = list(
                db.scalars(
                    select(Message)
                    .where(Message.task_id == task_id)
                    .order_by(Message.created_at.asc(), Message.id.asc())
                )
            )
            timeline = [
                {
                    "message_id": row.message_id,
                    "type": row.type,
                    "from": row.from_agent,
                    "to": row.to_agent,
                    "timestamp": row.timestamp,
                    "signature_status": signature_status_for(db, row),
                    "payload": row.payload_json,
                }
                for row in messages
            ]
            contribs = list(
                db.scalars(
                    select(Contribution)
                    .where(Contribution.task_id == task_id)
                    .order_by(Contribution.created_at.asc())
                )
            )
            return TEMPLATES.TemplateResponse(
                request,
                "task.html",
                {
                    "task": task_to_out(task),
                    "timeline": timeline,
                    "contributions": [contribution_to_out(c) for c in contribs],
                    "version": __version__,
                },
            )
        finally:
            db.close()

    @app.get("/ui/contributions", include_in_schema=False)
    def contributions_page(request: Request):
        db = get_session_factory()()
        try:
            rows = list(db.scalars(select(Contribution).order_by(Contribution.created_at.desc())))
            return TEMPLATES.TemplateResponse(
                request,
                "contributions.html",
                {"contributions": [contribution_to_out(c) for c in rows], "version": __version__},
            )
        finally:
            db.close()

    @app.get("/ui/contributions/{contrib_id}", include_in_schema=False)
    def contribution_page(request: Request, contrib_id: int):
        db = get_session_factory()()
        try:
            row = db.get(Contribution, contrib_id)
            if row is None:
                return TEMPLATES.TemplateResponse(
                    request,
                    "missing.html",
                    {"message": f"Contribution {contrib_id} not found", "version": __version__},
                    status_code=404,
                )
            return TEMPLATES.TemplateResponse(
                request,
                "contribution.html",
                {
                    "contribution": contribution_to_out(row),
                    "version": __version__,
                },
            )
        finally:
            db.close()

    @app.get("/ui/discover", include_in_schema=False)
    def discover_page(request: Request):
        db = get_session_factory()()
        try:
            raw = request.query_params.getlist("capability")
            if not raw:
                q = request.query_params.get("q") or ""
                raw = [p.strip() for p in q.split(",") if p.strip()]
            protocol = request.query_params.get("protocol") or ""
            status_filter = request.query_params.get("status") or ""
            verification = request.query_params.get("verification") or ""
            name_q = request.query_params.get("name") or ""
            did_q = request.query_params.get("did") or ""
            agents = list(
                db.scalars(select(Agent).options(selectinload(Agent.capabilities)).order_by(Agent.id))
            )
            public = _filter_public(
                [agent_to_out(a) for a in agents],
                protocol=protocol,
                status=status_filter,
                verification=verification,
                name_q=name_q,
                did_q=did_q,
            )
            allowed_ids = {a.id for a in public}
            items = []
            if raw:
                matching = [
                    a
                    for a in agents
                    if a.id in allowed_ids and {c.capability_id for c in a.capabilities} & set(raw)
                ]
                ranked = rank_agents(matching, raw, protocol=protocol or None)
                items = [
                    {
                        "agent": agent_to_out(a),
                        "rank": meta["rank"],
                        "breakdown": meta["rank_breakdown"],
                        "matched": meta["matched_capabilities"],
                    }
                    for a, meta in ranked
                ]
            elif protocol or status_filter or verification or name_q or did_q:
                items = [{"agent": a} for a in public]
            return TEMPLATES.TemplateResponse(
                request,
                "discover.html",
                {
                    "items": items,
                    "capabilities": raw,
                    "query": ",".join(raw),
                    "ranking": RANKING_DOC,
                    "protocol": protocol,
                    "status_filter": status_filter,
                    "verification": verification,
                    "name_q": name_q,
                    "did_q": did_q,
                    "protocol_options": protocol_values(public) or protocol_values([agent_to_out(a) for a in agents]),
                    "status_options": _STATUS_OPTIONS,
                    "verification_options": _VERIFICATION_OPTIONS,
                    "version": __version__,
                },
            )
        finally:
            db.close()

    @app.get("/ui/communicate", include_in_schema=False)
    def communicate_page(request: Request):
        from tar.schemas import TaskEventOut, TaskHistoryOut
        from tar.taxonomy import known_capability_ids

        db = get_session_factory()()
        try:
            agents = list(
                db.scalars(
                    select(Agent).options(selectinload(Agent.capabilities)).order_by(Agent.id)
                )
            )
            requester_id = (request.query_params.get("requester") or "").strip()
            assignee_id = (request.query_params.get("assignee") or "").strip()
            capability = (request.query_params.get("capability") or "").strip()
            task_id = (request.query_params.get("task_id") or "").strip()
            notice = request.query_params.get("notice") or None
            error = request.query_params.get("error") or None
            target = None
            if assignee_id:
                row = next((a for a in agents if a.id == assignee_id), None)
                if row is not None:
                    target = agent_to_out(row)
            task = None
            history = None
            if task_id:
                trow = db.get(Task, task_id)
                if trow is not None:
                    task = task_to_out(trow)
                    events = list(
                        db.scalars(
                            select(TaskEvent)
                            .where(TaskEvent.task_id == task_id)
                            .order_by(TaskEvent.created_at.asc(), TaskEvent.id.asc())
                        )
                    )
                    msgs = list(
                        db.scalars(
                            select(Message)
                            .where(Message.task_id == task_id)
                            .order_by(Message.created_at.asc(), Message.id.asc())
                        )
                    )
                    history = TaskHistoryOut(
                        task_id=task_id,
                        task=task,
                        events=[
                            TaskEventOut(
                                id=e.id,
                                task_id=e.task_id,
                                event=e.event,
                                actor_id=e.actor_id,
                                detail=e.detail or "",
                                created_at=e.created_at,
                            )
                            for e in events
                        ],
                        messages=[message_to_out(m) for m in msgs],
                    )
            return TEMPLATES.TemplateResponse(
                request,
                "communicate.html",
                {
                    "agents": [agent_to_out(a) for a in agents],
                    "requester_id": requester_id,
                    "assignee_id": assignee_id,
                    "capability": capability,
                    "description": request.query_params.get("description") or "",
                    "target": target,
                    "task": task,
                    "history": history,
                    "capability_ids": sorted(known_capability_ids()),
                    "notice": notice,
                    "error": error,
                    "result_text": "",
                    "version": __version__,
                },
            )
        finally:
            db.close()

    @app.post("/ui/communicate", include_in_schema=False)
    async def communicate_submit(request: Request):
        import json as _json

        from fastapi.responses import RedirectResponse

        form = await request.form()
        action = str(form.get("action") or "").strip()
        requester = str(form.get("requester") or "").strip()
        assignee = str(form.get("assignee") or "").strip()
        capability = str(form.get("capability") or "").strip()
        description = str(form.get("description") or "").strip()
        task_id = str(form.get("task_id") or "").strip()
        agent_id = str(form.get("agent_id") or "").strip()
        result_text = str(form.get("result_text") or "").strip()

        def _redirect(**params: str) -> RedirectResponse:
            from urllib.parse import urlencode

            q = {k: v for k, v in params.items() if v}
            return RedirectResponse(url=f"/ui/communicate?{urlencode(q)}", status_code=303)

        db = get_session_factory()()
        try:
            try:
                if action == "create":
                    task = create_task(
                        db,
                        requester=requester,
                        requested_capability=capability,
                        description=description
                        or "Analyse the tokenomics of Project X.",
                        assignee=assignee or None,
                    )
                    db.commit()
                    return _redirect(
                        requester=requester,
                        assignee=assignee,
                        capability=capability,
                        task_id=task.id,
                        notice=f"Task {task.id} created (REQUEST).",
                    )
                task = db.get(Task, task_id) if task_id else None
                if task is None:
                    return _redirect(
                        requester=requester,
                        assignee=assignee,
                        capability=capability,
                        error="Task not found.",
                    )
                if action == "accept":
                    accept_task(db, task, {"agent_id": agent_id or task.assignee_id})
                    db.commit()
                    return _redirect(
                        requester=requester or task.requester_id,
                        assignee=assignee or (task.assignee_id or ""),
                        capability=capability or task.requested_capability,
                        task_id=task.id,
                        notice="Task accepted.",
                    )
                if action == "reject":
                    reject_task(db, task, {"agent_id": agent_id or task.assignee_id})
                    db.commit()
                    return _redirect(
                        requester=requester or task.requester_id,
                        assignee=assignee or (task.assignee_id or ""),
                        capability=capability or task.requested_capability,
                        task_id=task.id,
                        notice="Task rejected.",
                    )
                if action == "submit":
                    result: object
                    if result_text:
                        try:
                            result = _json.loads(result_text)
                        except _json.JSONDecodeError:
                            result = {
                                "summary": result_text,
                                "token_supply": "TBD",
                                "allocation": "TBD",
                                "vesting": "TBD",
                            }
                    else:
                        result = {
                            "summary": "Demo tokenomics placeholder for Project X.",
                            "token_supply": "1_000_000_000",
                            "allocation": "Team 20% · Community 40% · Treasury 40%",
                            "vesting": "24-month linear with 6-month cliff",
                        }
                    submit_result(
                        db,
                        task,
                        {
                            "agent_id": agent_id or task.assignee_id,
                            "result": result,
                        },
                    )
                    db.commit()
                    return _redirect(
                        requester=requester or task.requester_id,
                        assignee=assignee or (task.assignee_id or ""),
                        capability=capability or task.requested_capability,
                        task_id=task.id,
                        notice="Result submitted (SUBMIT/RESULT).",
                    )
                return _redirect(
                    requester=requester,
                    assignee=assignee,
                    capability=capability,
                    error=f"Unknown action: {action}",
                )
            except WorkflowError as exc:
                db.rollback()
                return _redirect(
                    requester=requester,
                    assignee=assignee,
                    capability=capability,
                    task_id=task_id,
                    error=str(exc),
                )
        finally:
            db.close()

    @app.get("/ui/protocol", include_in_schema=False)
    def protocol_page(request: Request):
        return TEMPLATES.TemplateResponse(
            request,
            "protocol.html",
            {"example": EXAMPLE_MESSAGE, "version": __version__},
        )

    @app.get("/ui/protocol/schemas/{name}", include_in_schema=False)
    def protocol_schema(request: Request, name: str):
        if name not in _SCHEMA_FILES:
            return TEMPLATES.TemplateResponse(
                request,
                "missing.html",
                {"message": f"Schema {name} not found", "version": __version__},
                status_code=404,
            )
        path = SCHEMA_DIR / name
        if not path.is_file():
            return TEMPLATES.TemplateResponse(
                request,
                "missing.html",
                {"message": f"Schema {name} not found", "version": __version__},
                status_code=404,
            )
        return FileResponse(path, media_type="application/json", filename=name)

    @app.get("/ui/developers", include_in_schema=False)
    def developers_page(request: Request):
        return TEMPLATES.TemplateResponse(
            request,
            "developers.html",
            {"version": __version__},
        )


    @app.get("/ui/tclk", include_in_schema=False)
    def tclk_ui(request: Request):
        import json as _json

        from tar.models import TclkContract, TclkRoom
        from tar.tclk import (
            OFFER_ROOM_ID,
            agents_advertising_tclk,
            ensure_offer_room,
            list_transcript,
        )

        db = get_session_factory()()
        try:
            ensure_offer_room(db)
            db.commit()
            room_id = (request.query_params.get("room") or OFFER_ROOM_ID).strip()
            contract_id = (request.query_params.get("contract") or "").strip()
            rooms = list(db.scalars(select(TclkRoom).order_by(TclkRoom.id)))
            transcript = list_transcript(db, room_id) if db.get(TclkRoom, room_id) else []
            contract = db.get(TclkContract, contract_id) if contract_id else None
            contract_view = None
            if contract is not None:
                try:
                    state = _json.loads(contract.state_json or "{}")
                except _json.JSONDecodeError:
                    state = {}
                if isinstance(state, dict):
                    state.pop("secret", None)
                contract_view = {
                    "contract_id": contract.contract_id,
                    "protocol_status": contract.status,
                    "settlement_status": contract.settlement_status,
                    "paper_only": contract.paper_only == "true",
                    "rail": contract.rail,
                    "rail_ref": contract.rail_ref,
                    "payer_did": contract.payer_did,
                    "payee_did": contract.payee_did,
                    "state": state,
                }
            advertisers = [agent_to_out(a) for a in agents_advertising_tclk(db)]
            return TEMPLATES.TemplateResponse(
                request,
                "tclk.html",
                {
                    "rooms": rooms,
                    "room_id": room_id,
                    "transcript": transcript,
                    "contract": contract_view,
                    "contract_id": contract_id,
                    "advertisers": advertisers,
                    "version": __version__,
                },
            )
        finally:
            db.close()

    return app


app = create_app()
