"""FastAPI application factory for herdr-restful."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api import (
    agents,
    events,
    integrations,
    layout,
    notifications,
    panes,
    server,
    session,
    tabs,
    workspaces,
    worktrees,
)
from .config import settings
from .deps import call_herdr
from .herdr.client import HerdrClient

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.herdr = HerdrClient(settings.resolve_socket_path(), settings.request_timeout)
    logger.info("herdr socket: %s", app.state.herdr.socket_path)
    yield
    await app.state.herdr.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="herdr-restful",
        version=__version__,
        description=(
            "RESTful wrapper around the herdr local socket API.\n\n"
            "Resource-oriented endpoints for workspaces, tabs, panes and agents, "
            "with an SSE bridge for live events.\n\n"
            "**Response convention** — successful responses return the herdr "
            "`result` object verbatim (e.g. `{\"type\": \"pane_info\", \"pane\": {...}}`), "
            "so clients can rely on the upstream schema. "
            "**Errors** use `{\"detail\": {\"error\": {\"code\", \"message\"}}}` with an "
            "HTTP status derived from the herdr error code."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api = APIRouter()
    api.include_router(server.router)
    api.include_router(session.router)
    api.include_router(workspaces.router)
    api.include_router(worktrees.router)
    api.include_router(tabs.router)
    api.include_router(panes.router)
    api.include_router(agents.router)
    api.include_router(layout.router)
    api.include_router(events.router)
    api.include_router(notifications.router)
    api.include_router(integrations.router)
    app.include_router(api)

    @app.get("/api/v1/health", tags=["server"])
    async def health(request: Request) -> dict[str, Any]:
        """Liveness plus herdr reachability probe."""
        try:
            pong = await call_herdr(request, "ping", {})
            return {
                "status": "ok",
                "version": __version__,
                "herdr": pong,
                "socket": str(settings.resolve_socket_path()),
            }
        except Exception as exc:  # noqa: BLE001 - report any failure as degraded
            return {
                "status": "degraded",
                "version": __version__,
                "socket": str(settings.resolve_socket_path()),
                "error": str(exc),
            }

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"service": "herdr-restful", "docs": "/docs"}

    return app


app = create_app()


def run() -> None:
    """Console script entry point."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
