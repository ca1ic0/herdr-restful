"""Shared FastAPI dependencies and herdr call helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request

from .config import settings
from .herdr.client import HerdrClient
from .herdr.errors import HerdrApiError, HerdrTransportError, to_http_exception


def get_client(request: Request) -> HerdrClient:
    client = getattr(request.app.state, "herdr", None)
    if client is None:
        client = HerdrClient(settings.resolve_socket_path(), settings.request_timeout)
        request.app.state.herdr = client
    return client


async def call_herdr(
    request: Request, method: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Invoke a herdr socket method and translate failures to HTTP errors."""
    client = get_client(request)
    try:
        return await client.call(method, params)
    except HerdrApiError as exc:
        raise to_http_exception(exc) from exc
    except HerdrTransportError as exc:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "herdr_unavailable",
                    "message": str(exc),
                }
            },
        ) from exc


async def event_stream(request: Request) -> AsyncIterator[dict[str, Any]]:
    client = get_client(request)
    return client.subscribe()
