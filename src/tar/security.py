"""Auth, request-size cap, and a basic in-memory rate limit. Safe error bodies."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from tar.config import Settings, load_settings

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


async def require_registry_token(
    request: Request,
    x_registry_token: str | None = Header(default=None, alias="X-Registry-Token"),
) -> None:
    """If REGISTRY_TOKEN is set, mutating routes require X-Registry-Token.

    Unset token = open local demo. Documented in README and docs/api.md.
    """
    settings: Settings = getattr(request.app.state, "settings", None) or load_settings()
    if request.method not in MUTATING:
        return
    if not settings.auth_required:
        return
    if not x_registry_token or x_registry_token != settings.registry_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_body("unauthorized", "X-Registry-Token required for mutating routes"),
        )


class RequestLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_bytes: int = 65536, per_minute: int = 120):
        super().__init__(app)
        self.max_bytes = max_bytes
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next) -> Response:
        length = request.headers.get("content-length")
        if length is not None:
            try:
                if int(length) > self.max_bytes:
                    return JSONResponse(
                        status_code=413,
                        content=error_body("payload_too_large", "Request body exceeds size limit"),
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content=error_body("bad_request", "Invalid Content-Length"),
                )

        client = request.client.host if request.client else "unknown"
        now = time.time()
        window = self._hits[client]
        cutoff = now - 60
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= self.per_minute:
            return JSONResponse(
                status_code=429,
                content=error_body("rate_limited", "Too many requests; retry shortly"),
                headers={"Retry-After": "60"},
            )
        window.append(now)
        return await call_next(request)
