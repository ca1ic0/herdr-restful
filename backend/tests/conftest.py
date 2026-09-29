from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import create_app

from .fake_herdr import FakeHerdrServer, default_handler


def _short_socket_path() -> Path:
    """macOS caps AF_UNIX paths around 104 chars, so avoid pytest's tmp_path."""
    base = Path(os.environ.get("TMPDIR", "/tmp"))
    return base / f"hf-{uuid.uuid4().hex[:12]}.sock"


@pytest.fixture
async def fake_herdr() -> AsyncIterator[FakeHerdrServer]:
    server = FakeHerdrServer(_short_socket_path(), default_handler)
    await server.start()
    yield server
    await server.stop()


@pytest.fixture
async def app(fake_herdr: FakeHerdrServer):
    application = create_app()
    settings.socket_path = str(fake_herdr.socket_path)
    async with application.router.lifespan_context(application):
        yield application
    settings.socket_path = None


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
async def live_server(fake_herdr: FakeHerdrServer) -> AsyncIterator[str]:
    """Run the app under a real uvicorn server.

    httpx's ``ASGITransport`` awaits full app completion and therefore cannot
    drive an unbounded SSE stream, so those tests need a real server.
    """
    import uvicorn

    from app.config import settings as app_settings

    app_settings.socket_path = str(fake_herdr.socket_path)
    app_settings.sse_heartbeat = 1.0
    port = _free_port()
    config = uvicorn.Config(
        create_app(), host="127.0.0.1", port=port, log_level="warning", lifespan="on"
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    base = f"http://127.0.0.1:{port}"
    async with AsyncClient(base_url=base, timeout=10.0) as probe:
        for _ in range(100):
            try:
                await probe.get("/api/v1/health")
                break
            except Exception:
                await asyncio.sleep(0.05)
    yield base
    server.should_exit = True
    try:
        await asyncio.wait_for(task, timeout=5.0)
    except asyncio.TimeoutError:
        task.cancel()
    app_settings.socket_path = None
