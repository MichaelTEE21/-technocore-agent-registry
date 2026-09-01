"""ASGI app: REST API + HTML demo of a swarm of agents grouped by capability."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from starlette.exceptions import HTTPException as StarletteHTTPException

from tar import __version__
from tar.api import router
from tar.config import load_settings
from tar.db import get_session_factory, init_db
from tar.models import Agent, Contribution, Message, Swarm, Task
from tar.ranking import RANKING_DOC, rank_agents
from tar.security import RequestLimitMiddleware, error_body
from tar.serialize import agent_to_out, contribution_to_out, swarm_to_out, task_to_out
from tar.taxonomy import all_categories, list_capabilities
from tar.workflow import signature_status_for

PACKAGE = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(PACKAGE / "templates"))
STATIC = PACKAGE / "static"


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

    @app.get("/", include_in_schema=False)
    def home(request: Request):
        db = get_session_factory()()
        try:
            q = request.query_params.get("q") or ""
            cap = request.query_params.get("capability") or ""
            return TEMPLATES.TemplateResponse(
                request,
                "index.html",
                {
                    "agents": _agents(db, q or None, cap or None),
                    "query": q,
                    "capability": cap,
                    "version": __version__,
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
            return TEMPLATES.TemplateResponse(
                request,
                "agent.html",
                {
                    "agent": agent_to_out(agent),
                    "metrics": metrics_for(db, agent),
                    "contributions": [contribution_to_out(c) for c in contribs[:20]],
                    "version": __version__,
                },
            )
        finally:
            db.close()

    @app.get("/ui/capabilities", include_in_schema=False)
    def capabilities_page(request: Request):
        return TEMPLATES.TemplateResponse(
            request,
            "capabilities.html",
            {
                "categories": all_categories(),
                "items": list_capabilities(),
                "version": __version__,
            },
        )

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
            return TEMPLATES.TemplateResponse(
                request,
                "task.html",
                {
                    "task": task_to_out(task),
                    "timeline": timeline,
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

    @app.get("/ui/discover", include_in_schema=False)
    def discover_page(request: Request):
        db = get_session_factory()()
        try:
            raw = request.query_params.getlist("capability")
            if not raw:
                q = request.query_params.get("q") or ""
                raw = [p.strip() for p in q.split(",") if p.strip()]
            agents = list(
                db.scalars(select(Agent).options(selectinload(Agent.capabilities)).order_by(Agent.id))
            )
            items = []
            if raw:
                matching = [
                    a for a in agents if {c.capability_id for c in a.capabilities} & set(raw)
                ]
                ranked = rank_agents(matching, raw)
                items = [
                    {
                        "agent": agent_to_out(a),
                        "rank": meta["rank"],
                        "breakdown": meta["rank_breakdown"],
                        "matched": meta["matched_capabilities"],
                    }
                    for a, meta in ranked
                ]
            return TEMPLATES.TemplateResponse(
                request,
                "discover.html",
                {
                    "items": items,
                    "capabilities": raw,
                    "query": ",".join(raw),
                    "ranking": RANKING_DOC,
                    "version": __version__,
                },
            )
        finally:
            db.close()

    return app


app = create_app()
