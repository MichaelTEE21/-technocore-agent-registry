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
from tar.models import Agent, Swarm
from tar.security import RequestLimitMiddleware, error_body
from tar.serialize import agent_to_out, swarm_to_out

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
            "An open-source reference implementation and proposal for agent "
            "capability discovery within the Technocore ecosystem. "
            "A swarm of agents that can be discovered and grouped by capability. "
            "Not an official Technocore component."
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

    @app.get("/", include_in_schema=False)
    def home(request: Request):
        db = get_session_factory()()
        try:
            agents = list(
                db.scalars(select(Agent).options(selectinload(Agent.capabilities)).order_by(Agent.id))
            )
            q = request.query_params.get("capability") or request.query_params.get("q")
            if q:
                agents = [
                    a
                    for a in agents
                    if q.lower() in a.name.lower()
                    or q.lower() in a.id.lower()
                    or any(q.lower() in c.capability_id.lower() for c in a.capabilities)
                ]
            return TEMPLATES.TemplateResponse(
                request,
                "index.html",
                {
                    "agents": [agent_to_out(a) for a in agents],
                    "query": q or "",
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
            return TEMPLATES.TemplateResponse(
                request,
                "agent.html",
                {"agent": agent_to_out(agent), "version": __version__},
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
                items.append(
                    swarm_to_out(swarm, members=[agent_to_out(a) for a in members])
                )
            return TEMPLATES.TemplateResponse(
                request,
                "swarms.html",
                {"swarms": items, "version": __version__},
            )
        finally:
            db.close()

    return app


app = create_app()
