from __future__ import annotations

import pytest

from app.herdr.errors import HerdrApiError, status_for


@pytest.mark.parametrize(
    "code,expected",
    [
        ("not_found", 404),
        ("workspace_not_found", 404),
        ("pane_not_found", 404),
        ("agent_not_found", 404),
        ("tab_not_found", 404),
        ("invalid_params", 422),
        ("invalid_request", 400),
        ("agent_blocked", 409),
        ("stream_conflict", 409),
        ("workspace_group_close_required", 409),
        ("popup_not_open", 409),
        ("plugin_disabled", 409),
        ("not_git_worktree", 409),
        ("same_tab", 409),
        ("platform_unsupported", 400),
        ("feature_disabled", 501),
        ("rate_limited", 429),
        ("request_timeout", 504),
        ("unrecognized_code", 502),
    ],
)
def test_status_for(code: str, expected: int) -> None:
    assert status_for(code) == expected


def test_api_error_from_payload() -> None:
    exc = HerdrApiError.from_payload({"code": "pane_not_found", "message": "nope"})
    assert exc.code == "pane_not_found"
    assert exc.message == "nope"
