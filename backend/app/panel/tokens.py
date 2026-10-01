"""Generate per-device panel tokens.

Usage::

    python -m app.panel.tokens

Print a fresh random token to give to one device (entered on the provisioning
page) plus the settings line for the gateway. The gateway compares digests,
so losing the printed token means generating a new one; there is no list of
issued tokens to leak. Revoke a device by removing its token from
``HERDR_RESTFUL_PANEL_TOKENS`` and restarting the gateway.
"""

from __future__ import annotations

import secrets

from .auth import token_digest


def generate_token() -> str:
    return "hp_" + secrets.token_urlsafe(24)


def main() -> None:
    token = generate_token()
    print(f"device token (enter on the panel provisioning page):\n  {token}")
    print(f"sha256 (for audit only, not needed by the gateway):\n  {token_digest(token)}")
    print("\ngateway setting (append, comma separated):")
    print(f"  HERDR_RESTFUL_PANEL_TOKENS={token}")


if __name__ == "__main__":
    main()
