"""Short-lived HMAC-signed context tokens for panel actions.

A context token binds one pending card as seen at detail time: server boot,
terminal, pane, agent kind, the fingerprint of the evidence lines and the
offered choices. The action endpoint re-reads the live terminal and refuses
to send keys unless the freshly computed fingerprint matches the token.

Tokens expire after ``settings.panel_context_ttl`` seconds. The signing
secret is random per gateway boot unless configured, so tokens never survive
a restart (neither does ``server_id``).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field

from ..config import settings

_SCHEMA = 1

_boot_secret: str | None = None


def _secret() -> bytes:
    global _boot_secret
    if settings.panel_secret:
        return settings.panel_secret.encode("utf-8")
    if _boot_secret is None:
        _boot_secret = secrets.token_hex(32)
    return _boot_secret.encode("utf-8")


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def fingerprint(evidence: list[str], choices: list[str], extra: str = "") -> str:
    """Stable digest of what the user was shown when they decided."""
    h = hashlib.sha256()
    h.update("\x1f".join(evidence).encode("utf-8", "replace"))
    h.update(b"\x1e")
    h.update(",".join(sorted(choices)).encode("ascii"))
    if extra:
        h.update(b"\x1e")
        h.update(extra.encode("utf-8", "replace"))
    return h.hexdigest()


class ContextInvalid(Exception):
    """Raised when a context token cannot be trusted for a new decision."""


@dataclass
class PanelContext:
    server_id: str
    terminal_id: str
    pane_id: str
    agent: str
    fp: str
    choices: list[str] = field(default_factory=list)
    expires_at: float = 0.0


def issue(ctx: PanelContext) -> str:
    payload = {
        "v": _SCHEMA,
        "sid": ctx.server_id,
        "tid": ctx.terminal_id,
        "pid": ctx.pane_id,
        "ag": ctx.agent,
        "fp": ctx.fp,
        "ch": ctx.choices,
        "exp": ctx.expires_at,
    }
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    mac = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64e(mac)}"


def verify(token: str, *, server_id: str, terminal_id: str) -> PanelContext:
    try:
        body, mac = token.split(".", 1)
    except ValueError as exc:
        raise ContextInvalid("malformed context token") from exc
    expected = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest()
    try:
        given = _b64d(mac)
    except Exception as exc:  # noqa: BLE001 - any decode failure is invalid
        raise ContextInvalid("malformed context token") from exc
    if not hmac.compare_digest(expected, given):
        raise ContextInvalid("bad context token signature")
    try:
        payload = json.loads(_b64d(body))
    except Exception as exc:  # noqa: BLE001
        raise ContextInvalid("malformed context token") from exc

    if payload.get("v") != _SCHEMA:
        raise ContextInvalid("unknown context token version")
    if payload.get("sid") != server_id or payload.get("tid") != terminal_id:
        raise ContextInvalid("context token belongs to a different terminal")
    exp = float(payload.get("exp") or 0)
    if exp < time.time():
        raise ContextInvalid("context token expired")

    return PanelContext(
        server_id=payload["sid"],
        terminal_id=payload["tid"],
        pane_id=str(payload.get("pid") or ""),
        agent=str(payload.get("ag") or ""),
        fp=str(payload.get("fp") or ""),
        choices=[str(c) for c in payload.get("ch") or []],
        expires_at=exp,
    )
