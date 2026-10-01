"""SQLite-backed idempotency records for panel actions.

Every action request_id is written *before* any key is sent, with result
``uncertain``. A replay of the same id with the same body returns the
recorded result without sending again; the same id with a different body is
rejected. Records are kept well past the 10 minute contract, then pruned.
"""

from __future__ import annotations

import asyncio
import sqlite3
import threading
import time
from pathlib import Path

RETENTION_SECONDS = 3600  # contract requires >= 600

RESULT_UNCERTAIN = "uncertain"


class ActionStore:
    def __init__(self, path: Path):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(self._path), check_same_thread=False)
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS panel_actions (
                request_id  TEXT PRIMARY KEY,
                terminal_id TEXT NOT NULL,
                body_hash   TEXT NOT NULL,
                result      TEXT NOT NULL,
                message     TEXT NOT NULL DEFAULT '',
                created_at  REAL NOT NULL
            )
            """
        )
        self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # sync internals run under a thread lock; async wrappers keep the loop free

    def _lookup(self, request_id: str) -> dict | None:
        row = self._db.execute(
            "SELECT terminal_id, body_hash, result, message, created_at"
            " FROM panel_actions WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "terminal_id": row[0],
            "body_hash": row[1],
            "result": row[2],
            "message": row[3],
            "created_at": row[4],
        }

    def _insert(self, request_id: str, terminal_id: str, body_hash: str) -> bool:
        try:
            self._db.execute(
                "INSERT INTO panel_actions"
                " (request_id, terminal_id, body_hash, result, message, created_at)"
                " VALUES (?, ?, ?, ?, '', ?)",
                (request_id, terminal_id, body_hash, RESULT_UNCERTAIN, time.time()),
            )
            self._db.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def _set_result(self, request_id: str, result: str, message: str) -> None:
        self._db.execute(
            "UPDATE panel_actions SET result = ?, message = ? WHERE request_id = ?",
            (result, message, request_id),
        )
        self._db.commit()

    def _prune(self) -> None:
        self._db.execute(
            "DELETE FROM panel_actions WHERE created_at < ?",
            (time.time() - RETENTION_SECONDS,),
        )
        self._db.commit()

    async def lookup(self, request_id: str) -> dict | None:
        return await asyncio.to_thread(self._with_lock, self._lookup, request_id)

    async def insert(self, request_id: str, terminal_id: str, body_hash: str) -> bool:
        return await asyncio.to_thread(
            self._with_lock, self._insert, request_id, terminal_id, body_hash
        )

    async def set_result(self, request_id: str, result: str, message: str) -> None:
        await asyncio.to_thread(self._with_lock, self._set_result, request_id, result, message)

    async def prune(self) -> None:
        await asyncio.to_thread(self._with_lock, self._prune)

    def _with_lock(self, fn, *args):
        with self._lock:
            return fn(*args)
