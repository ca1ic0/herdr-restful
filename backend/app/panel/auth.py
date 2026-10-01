"""Per-device bearer authentication for the panel API.

Tokens are configured on the host (``HERDR_RESTFUL_PANEL_TOKENS``, comma
separated) and only ever compared as SHA-256 digests with constant-time
comparison. Use ``python -m app.panel.tokens`` to generate a device token.

Comparison is normalised (lowercase, alphanumeric only) so short pairing
codes may be typed with or without dashes and in any case. Failed attempts
are throttled per client IP with exponential backoff — this is what makes
a 12-char (60-bit) code safe against online guessing.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import time

from fastapi import HTTPException, Request

from ..config import settings

logger = logging.getLogger(__name__)

# client IP -> (consecutive failures, blocked until monotonic ts)
_failures: dict[str, tuple[int, float]] = {}
_backoff_lock = asyncio.Lock()

_MAX_BACKOFF_S = 30.0


def normalize_token(token: str) -> str:
    """Case- and separator-insensitive form; hashing this is what matters."""
    return "".join(ch for ch in token.lower() if ch.isalnum())


def token_digest(token: str) -> str:
    return hashlib.sha256(normalize_token(token).encode("utf-8")).hexdigest()


def _configured_digests() -> list[str]:
    return [token_digest(t) for t in settings.panel_token_list]


def _reject(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"error": {"code": code, "message": message}},
    )


async def _throttled(ip: str) -> bool:
    async with _backoff_lock:
        _, until = _failures.get(ip, (0, 0.0))
        return time.monotonic() < until


async def _record_failure(ip: str) -> None:
    async with _backoff_lock:
        count, _ = _failures.get(ip, (0, 0.0))
        count += 1
        delay = min(0.5 * (2 ** min(count, 6)), _MAX_BACKOFF_S)
        _failures[ip] = (count, time.monotonic() + delay)


async def _clear_failures(ip: str) -> None:
    async with _backoff_lock:
        _failures.pop(ip, None)


def reset_auth_backoff() -> None:
    """Test hook: forget all per-IP backoff state."""
    _failures.clear()


async def require_device(request: Request) -> str:
    """FastAPI dependency: enforce a valid per-device Bearer token."""
    digests = _configured_digests()
    if not digests:
        raise _reject(
            503,
            "panel_not_configured",
            "gateway has no panel device tokens configured",
        )

    ip = request.client.host if request.client else "unknown"
    if await _throttled(ip):
        raise _reject(429, "rate_limited", "too many failed attempts; wait and retry")

    authorization = request.headers.get("authorization")
    if authorization is None or not authorization.startswith("Bearer "):
        # not a guess attempt (probes, browsers) — don't count toward backoff
        raise _reject(401, "unauthorized", "missing device bearer token")

    presented = token_digest(authorization[len("Bearer ") :].strip())
    if any(hmac.compare_digest(presented, d) for d in digests):
        await _clear_failures(ip)
        return "device"

    await _record_failure(ip)
    logger.warning("panel auth failure from %s", ip)
    await asyncio.sleep(0.25)  # slow down online guessing
    raise _reject(401, "unauthorized", "invalid device token")
