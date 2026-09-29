"""Async client for the herdr newline-delimited JSON socket protocol.

Transport notes (verified against herdr 0.9.0):

* Plain request/response calls use **one connection per request**: herdr
  writes the response line and then closes the socket. Opening a fresh
  connection for every call is therefore required, not an optimisation.
* ``events.subscribe`` keeps the connection open and pushes ``event`` frames
  after the acknowledgement response.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator, Callable, Iterable
from pathlib import Path
from typing import Any

from .errors import HerdrApiError, HerdrTransportError

logger = logging.getLogger(__name__)

MAX_LINE_BYTES = 64 * 1024 * 1024
DEFAULT_CONCURRENCY = 64


async def _read_frame(
    reader: asyncio.StreamReader, what: str
) -> dict[str, Any]:
    try:
        line = await reader.readline()
    except (asyncio.IncompleteReadError, ConnectionError, OSError) as exc:
        raise HerdrTransportError(f"herdr connection dropped during {what}: {exc}") from exc
    if not line:
        raise HerdrTransportError(f"herdr closed the connection without answering {what}")
    try:
        return json.loads(line)
    except json.JSONDecodeError as exc:
        raise HerdrTransportError(f"herdr sent a malformed frame for {what}") from exc


def _raise_for_error(msg: dict[str, Any]) -> dict[str, Any]:
    if msg.get("error") is not None:
        raise HerdrApiError.from_payload(msg["error"])
    return msg.get("result", {})


class HerdrClient:
    """herdr socket client used by the REST layer."""

    def __init__(
        self,
        socket_path: Path,
        request_timeout: float = 15.0,
        max_concurrency: int = DEFAULT_CONCURRENCY,
    ):
        self._path = Path(socket_path)
        self._timeout = request_timeout
        self._sem = asyncio.Semaphore(max_concurrency)

    @property
    def socket_path(self) -> Path:
        return self._path

    def use_socket(self, path: Path) -> None:
        """Point the client at a different socket (tests / reconfiguration)."""
        self._path = Path(path)

    async def _connect(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        try:
            return await asyncio.open_unix_connection(str(self._path), limit=MAX_LINE_BYTES)
        except (FileNotFoundError, ConnectionRefusedError, OSError) as exc:
            raise HerdrTransportError(
                f"cannot connect to herdr socket at {self._path}: {exc}"
            ) from exc

    async def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Send one request on a dedicated connection and return its ``result``."""
        req_id = uuid.uuid4().hex
        payload = {"id": req_id, "method": method, "params": params or {}}
        limit = timeout or self._timeout

        async with self._sem:
            reader, writer = await self._connect()
            try:
                writer.write((json.dumps(payload) + "\n").encode("utf-8"))
                await writer.drain()
                msg = await asyncio.wait_for(_read_frame(reader, method), timeout=limit)
                return _raise_for_error(msg)
            except asyncio.TimeoutError as exc:
                raise HerdrTransportError(
                    f"herdr request {method} timed out after {limit}s"
                ) from exc
            except (ConnectionError, OSError) as exc:
                raise HerdrTransportError(f"failed to talk to herdr: {exc}") from exc
            finally:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:  # pragma: no cover - best effort teardown
                    pass

    async def ping(self) -> dict[str, Any]:
        return await self.call("ping", {})

    async def subscribe(
        self,
        subscriptions: Iterable[dict[str, Any]] | None = None,
        on_subscribed: Callable[[], None] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Open a dedicated connection, subscribe, and yield pushed events.

        ``subscriptions`` is required by the herdr protocol; pass an empty list
        to subscribe to nothing. ``on_subscribed`` runs once herdr has
        acknowledged the subscription. The acknowledgement response is
        consumed first; only subsequent frames are yielded as events.
        """
        req_id = uuid.uuid4().hex
        params: dict[str, Any] = {
            "subscriptions": list(subscriptions) if subscriptions is not None else []
        }

        reader, writer = await self._connect()
        try:
            writer.write(
                (
                    json.dumps(
                        {"id": req_id, "method": "events.subscribe", "params": params}
                    )
                    + "\n"
                ).encode("utf-8")
            )
            await writer.drain()

            ack = await _read_frame(reader, "events.subscribe")
            if ack.get("id") == req_id:
                _raise_for_error(ack)
            if on_subscribed is not None:
                on_subscribed()

            while True:
                line = await reader.readline()
                if not line:
                    return
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if msg.get("id") == req_id:
                    continue
                yield msg
        except (ConnectionError, OSError) as exc:
            raise HerdrTransportError(f"herdr event stream broke: {exc}") from exc
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:  # pragma: no cover - best effort teardown
                pass

    async def close(self) -> None:
        """No persistent connections to tear down; kept for lifecycle symmetry."""
        return None
