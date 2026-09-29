"""Error mapping between herdr socket error codes and HTTP semantics."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field


class HerdrErrorPayload(BaseModel):
    """Shape of an ``error`` object returned by the herdr socket API."""

    code: str
    message: str | None = None
    data: Any | None = None

    model_config = {"extra": "allow"}


class HerdrApiError(Exception):
    """Raised when herdr answers a request with an ``error`` object."""

    def __init__(self, code: str, message: str | None = None, data: Any | None = None):
        self.code = code
        self.message = message or code
        self.data = data
        super().__init__(f"{code}: {self.message}")

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "HerdrApiError":
        parsed = HerdrErrorPayload.model_validate(payload)
        return cls(parsed.code, parsed.message, parsed.data)


class HerdrTransportError(Exception):
    """Raised when the herdr socket cannot be reached or the stream breaks."""


# herdr error code -> HTTP status code. Codes not listed here are matched by
# the patterns in ``status_for`` below; herdr does not publish a closed enum.
ERROR_STATUS: dict[str, int] = {
    "not_found": 404,
    "invalid_params": 422,
    "invalid_request": 400,
    "unauthorized": 403,
    "forbidden": 403,
    "platform_unsupported": 400,
    "feature_disabled": 501,
    "rate_limited": 429,
    "timeout": 504,
    "internal_error": 502,
}

DEFAULT_ERROR_STATUS = 502

# Ordered pattern rules, first match wins.
_STATUS_RULES: list[tuple[str, int]] = [
    ("_not_found", 404),
    ("_not_open", 409),
    ("_required", 409),
    ("_conflict", 409),
    ("_disabled", 409),
    ("_unsupported", 400),
    ("_timeout", 504),
    ("_limit", 429),
    ("_blocked", 409),
    ("already_", 409),
    ("same_tab", 409),
    ("same_pane", 409),
    ("not_git_", 409),
    ("no_", 409),
    ("busy", 409),
    ("invalid_", 422),
]


def status_for(code: str) -> int:
    if code in ERROR_STATUS:
        return ERROR_STATUS[code]
    for needle, status in _STATUS_RULES:
        if code.startswith(needle) or code.endswith(needle):
            return status
    return DEFAULT_ERROR_STATUS


def to_http_exception(exc: HerdrApiError) -> HTTPException:
    return HTTPException(
        status_code=status_for(exc.code),
        detail={"error": {"code": exc.code, "message": exc.message, "data": exc.data}},
    )


class OkResponse(BaseModel):
    """Uniform envelope returned by endpoints with no richer payload."""

    ok: bool = True
    result: dict[str, Any] = Field(default_factory=dict)
