"""Per-device bearer authentication for the panel API.

Tokens are configured on the host (``HERDR_RESTFUL_PANEL_TOKENS``, comma
separated) and only ever compared as SHA-256 digests with constant-time
comparison. Use ``python -m app.panel.tokens`` to generate a device token.
"""

from __future__ import annotations

import hashlib
import hmac

from fastapi import Header, HTTPException

from ..config import settings


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _configured_digests() -> list[str]:
    return [token_digest(t) for t in settings.panel_token_list]


def _reject(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"error": {"code": code, "message": message}},
    )


async def require_device(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency: enforce a valid per-device Bearer token."""
    digests = _configured_digests()
    if not digests:
        raise _reject(
            503,
            "panel_not_configured",
            "gateway has no panel device tokens configured",
        )
    if authorization is None or not authorization.startswith("Bearer "):
        raise _reject(401, "unauthorized", "missing device bearer token")
    presented = token_digest(authorization[len("Bearer ") :].strip())
    if not any(hmac.compare_digest(presented, d) for d in digests):
        raise _reject(401, "unauthorized", "invalid device token")
    return "device"
