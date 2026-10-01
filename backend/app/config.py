"""Runtime configuration and herdr socket path resolution.

Resolution order matches the herdr documentation:

1. ``HERDR_SOCKET_PATH`` (explicit low-level override)
2. ``HERDR_SESSION`` / configured ``session`` name -> ``<config>/sessions/<name>/herdr.sock``
3. default session socket ``<config>/herdr.sock``
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_herdr_config_dir() -> Path:
    """Return the herdr configuration directory for this platform."""
    override = os.environ.get("HERDR_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "herdr"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HERDR_RESTFUL_", extra="ignore")

    host: str = Field(default="127.0.0.1", description="Bind address for the REST API")
    port: int = Field(default=8080, description="Bind port for the REST API")
    session: str | None = Field(default=None, description="Named herdr session, if any")
    socket_path: str | None = Field(
        default=None,
        description="Explicit herdr socket path; overrides session resolution",
    )
    request_timeout: float = Field(
        default=15.0, description="Timeout in seconds for socket request/response calls"
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed CORS origins for the validation frontend",
    )
    sse_heartbeat: float = Field(default=15.0, description="SSE heartbeat interval in seconds")

    # device panel gateway (/api/v1/panel)
    panel_tokens: str = Field(
        default="",
        description="Comma-separated per-device bearer tokens for the panel API",
    )
    panel_secret: str | None = Field(
        default=None,
        description="HMAC secret for panel context tokens; random per boot if unset",
    )
    panel_db_path: str | None = Field(
        default=None,
        description="SQLite path for panel action idempotency records",
    )
    panel_context_ttl: float = Field(
        default=10.0, description="Seconds a panel context token stays valid"
    )
    panel_continue_prompt: str = Field(
        default="继续当前任务，并先说明下一步。",
        description="Prompt text sent by the panel 'continue' action",
    )

    @property
    def herdr_config_dir(self) -> Path:
        return default_herdr_config_dir()

    @property
    def panel_token_list(self) -> list[str]:
        return [t.strip() for t in self.panel_tokens.split(",") if t.strip()]

    def resolve_panel_db_path(self) -> Path:
        if self.panel_db_path:
            return Path(self.panel_db_path).expanduser()
        return self.herdr_config_dir / "panel_actions.db"

    def resolve_socket_path(self) -> Path:
        """Resolve the herdr socket path using the documented precedence."""
        explicit = self.socket_path or os.environ.get("HERDR_SOCKET_PATH")
        if explicit:
            return Path(explicit).expanduser()

        session = self.session or os.environ.get("HERDR_SESSION")
        config_dir = self.herdr_config_dir
        if session:
            return config_dir / "sessions" / session / "herdr.sock"
        return config_dir / "herdr.sock"


settings = Settings()
