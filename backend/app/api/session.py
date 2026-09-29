"""Session bootstrap snapshot."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from ..deps import call_herdr

router = APIRouter(prefix="/api/v1/session", tags=["session"])


@router.get("/snapshot")
async def snapshot(request: Request) -> dict[str, Any]:
    """One-shot bootstrap snapshot used to seed clients (``session.snapshot``)."""
    return await call_herdr(request, "session.snapshot", {})
