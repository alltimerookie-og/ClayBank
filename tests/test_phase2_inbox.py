"""Unit tests for P2-08: Inbox View Shell."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import pytest

from app.views.inbox_view import InboxView, UnfiledSaveItem

FIXTURES_PATH = Path("Docs/api/fixtures")


def test_inbox_empty_state() -> None:
    """Verify empty inbox shows 'Your inbox is clear' and paste link trigger."""
    add_link_triggered = False

    def on_add() -> None:
        nonlocal add_link_triggered
        add_link_triggered = True

    view = InboxView(
        saves=[],
        suggestions=[],
        active_jobs=[],
        on_add_link=on_add,
    )

    assert view.empty_state_container.visible is True
    assert view.empty_state_title.value == "Your inbox is clear"
    assert view.empty_state_button.content == "Paste a link"

    view.trigger_add_link()
    assert add_link_triggered is True


def test_inbox_populated_from_fixtures() -> None:
    """Verify inbox binds processing, suggestions, recent saves, and unfiled stream."""
    save_page_fix = json.loads((FIXTURES_PATH / "save-page.fixtures.json").read_text(encoding="utf-8"))
    sugg_fix = json.loads((FIXTURES_PATH / "suggestion.fixtures.json").read_text(encoding="utf-8"))
    job_fix = json.loads((FIXTURES_PATH / "job.fixtures.json").read_text(encoding="utf-8"))

    saves = save_page_fix["valid"][0]["items"]
    suggestions = sugg_fix["valid"][:2]
    jobs = job_fix["valid"][:1]

    view = InboxView(
        saves=saves,
        suggestions=suggestions,
        active_jobs=jobs,
    )

    assert view.empty_state_container.visible is False
    assert view.processing_column.visible is True
    assert view.suggestions_column.visible is True
    assert view.recent_carousel.visible is True
    assert view.stream_column.visible is True

    # Processing column has header + 1 card
    assert len(view.processing_column.controls) == 2

    # Suggestions column has header + 2 cards
    assert len(view.suggestions_column.controls) == 3

    # Stream column has header + 1 card
    assert len(view.stream_column.controls) == 2


def test_inbox_loading_and_error_states() -> None:
    """Verify loading indicator and error banner behavior."""
    view = InboxView(is_loading=True)
    assert view.loading_indicator.visible is True

    view.set_loading(False)
    assert view.loading_indicator.visible is False

    view.set_error("Failed to connect to ClayBank backend")
    assert view.error_banner.visible is True
    assert "Failed to connect" in view.error_banner_text.value

    view.set_error(None)
    assert view.error_banner.visible is False


def test_inbox_degraded_save_presentation() -> None:
    """Verify degraded/unknown kind displays degraded badge without crash."""
    degraded_item = {
        "id": "save-deg-1",
        "url": "https://example.com/unknown-format.bin",
        "kind": "unknown",
        "platform": "web",
        "captured_at": "2026-10-31T12:00:00Z",
    }

    card = UnfiledSaveItem(degraded_item)
    assert card.degraded_badge.visible is True
    assert card.title_text.value == "example.com"


def test_inbox_refresh_callback() -> None:
    """Verify refresh button invokes on_refresh callback."""
    refreshed = False

    def on_ref() -> None:
        nonlocal refreshed
        refreshed = True

    view = InboxView(on_refresh=on_ref)
    view.refresh()
    assert refreshed is True
