"""User notification endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from ..deps import call_herdr
from ..schemas.models import NotificationShow

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.post("")
async def show_notification(request: Request, body: NotificationShow) -> dict[str, Any]:
    return await call_herdr(request, "notification.show", body.model_dump(exclude_none=True))
