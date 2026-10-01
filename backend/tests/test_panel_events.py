from types import SimpleNamespace

import pytest

from app.panel.events import PanelEventStore


def agent(status: str):
    return SimpleNamespace(terminal_id="term-a", agent="claude", herdr_status=status)


def test_cursor_pagination_and_retention_gap():
    store = PanelEventStore("server-1")
    baseline = store.page(None, 16)["next_cursor"]
    store.observe([agent("working")])
    for _ in range(270):
        store.observe([agent("blocked")])
        store.observe([agent("working")])

    first = store.page(baseline, 16)
    assert first["gap"] is True
    assert first["events"] == []

    current = store.page(None, 16)["next_cursor"]
    store.observe([agent("blocked")])
    store.observe([agent("working")])
    store.observe([agent("blocked")])
    page = store.page(current, 1)
    assert page["has_more"] is True
    assert len(page["events"]) == 1
    next_page = store.page(page["next_cursor"], 1)
    assert next_page["has_more"] is False
    assert len(next_page["events"]) == 1


def test_invalid_cursor_rejected():
    store = PanelEventStore("server-1")
    with pytest.raises(ValueError):
        store.page("/etc/passwd", 16)
