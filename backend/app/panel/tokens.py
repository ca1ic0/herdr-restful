"""Generate per-device panel credentials.

Usage::

    python -m app.panel.tokens            # human-typed pairing code (default)
    python -m app.panel.tokens --long     # 192-bit token for automation

The short code is 12 chars from a 32-symbol unambiguous alphabet (no 0/O/1/I),
i.e. 60 bits of entropy — safe online because the gateway backs off
exponentially on auth failures. Comparison is case- and dash-insensitive,
so humans may type it however it is easiest. Print once; revoke by removing
it from ``HERDR_RESTFUL_PANEL_TOKENS`` and restarting the gateway.
"""

from __future__ import annotations

import secrets
import sys

from .auth import token_digest

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # Crockford-style, no 0/O/1/I


def generate_code(groups: int = 3, group_len: int = 4) -> str:
    """Human-typed pairing code, e.g. ``K7QX-2M9T-W4HB`` (60 bits)."""
    raw = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(groups * group_len))
    return "-".join(raw[i : i + group_len] for i in range(0, len(raw), group_len))


def generate_token() -> str:
    """Long token (192 bits) for automation where nobody types it."""
    return "hp_" + secrets.token_urlsafe(24)


def main() -> None:
    if "--long" in sys.argv[1:]:
        token = generate_token()
        print(f"device token (192-bit, for automation):\n  {token}")
    else:
        token = generate_code()
        print(f"pairing code (type this on the panel provisioning page):\n  {token}")
    print(f"sha256 (audit only): {token_digest(token)}")
    print("\ngateway setting (append, comma separated):")
    print(f"  HERDR_RESTFUL_PANEL_TOKENS={token}")


if __name__ == "__main__":
    main()
