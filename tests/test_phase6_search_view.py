"""Unit tests for SearchView (Phase 6 deliverable P6-02)."""

from typing import Any
import flet as ft
import pytest

from app.views.search.search_result_card import SearchResultCard
from app.views.search.search_view import (
    FACET_ALL,
    FACET_INSTAGRAM,
    FACET_THIS_MONTH,
    FACET_YOUTUBE,
    SearchView,
    filter_results_by_facet,
)

SAMPLE_RESULTS = [
    {
        "save": {
            "id": "018f4c1a-0000-7de6-9c8e-000000000001",
            "title": "Creamy garlic pasta",
            "url": "https://www.instagram.com/reel/Cx9abc/",
            "platform": "instagram",
            "captured_at": "2026-10-31T12:00:00Z",
        },
        "match_reason": "transcript",
        "fragment": "add cream at the end",
        "jump_target": "0:42",
        "score": 0.98,
    },
    {
        "save": {
            "id": "018f4c1a-0000-7de6-9c8e-000000000002",
            "title": "One pot pasta",
            "url": "https://www.youtube.com/watch?v=xyz123",
            "platform": "youtube",
            "captured_at": "2026-10-30T10:00:00Z",
        },
        "match_reason": "title",
        "fragment": "One pot pasta",
        "jump_target": None,
        "score": 0.81,
    },
]


def test_search_view_initial_state():
    """Verify initial state of SearchView before query execution."""
    view = SearchView(initial_query="")

    assert view.query == ""
    assert view.search_input.value == ""
    assert view.search_input.autofocus is True
    assert view.clear_button.visible is False
    assert view.ask_banner is not None
    assert view.recent_column.visible is True
    assert len(view.results_column.controls) == 0


def test_search_view_ask_banner_click():
    """Verify tapping Ask banner triggers on_open_ask with scope."""
    opened_scope: list[str | None] = []
    view = SearchView(
        folder_scope="folder-123",
        on_open_ask=lambda scope: opened_scope.append(scope),
    )

    view._handle_open_ask()
    assert opened_scope == ["folder-123"]


def test_search_view_query_submit_and_results():
    """Verify executing search renders results summary and SearchResultCard controls."""
    searched_queries: list[str] = []

    def mock_search(q: str, scope: str | None, cursor: str | None):
        searched_queries.append(q)
        return {"results": SAMPLE_RESULTS, "cursor": None}

    view = SearchView(on_search=mock_search)
    view.submit_search("pasta")

    assert searched_queries == ["pasta"]
    assert view.query == "pasta"
    assert view.clear_button.visible is True
    assert view.recent_column.visible is False
    assert view.results_summary.visible is True
    assert "2 results · keyword + meaning" in view.results_summary.value
    assert len(view.results_column.controls) == 2
    assert isinstance(view.results_column.controls[0], SearchResultCard)


def test_search_view_empty_results():
    """Verify empty state message when search returns 0 results."""
    view = SearchView(on_search=lambda q, s, c: {"results": [], "cursor": None})
    view.submit_search("unknownqueryxyz")

    assert len(view.results_column.controls) == 1
    empty_container = view.results_column.controls[0]
    assert isinstance(empty_container, ft.Container)
    text_ctrl = empty_container.content
    assert isinstance(text_ctrl, ft.Text)
    assert "No matches found for 'unknownqueryxyz'" in text_ctrl.value


def test_search_view_clear():
    """Verify clear button clears query and restores recent query suggestions."""
    view = SearchView(initial_query="pasta")
    view.set_results(SAMPLE_RESULTS)
    assert len(view.results_column.controls) == 2

    view.clear_search()
    assert view.query == ""
    assert view.search_input.value == ""
    assert view.clear_button.visible is False
    assert len(view.results_column.controls) == 0
    assert view.recent_column.visible is True


def test_search_view_facet_filtering():
    """Verify client-side facet filtering on loaded search results."""
    # 1. YouTube facet
    yt_results = filter_results_by_facet(SAMPLE_RESULTS, FACET_YOUTUBE)
    assert len(yt_results) == 1
    assert yt_results[0]["save"]["platform"] == "youtube"

    # 2. Instagram facet
    ig_results = filter_results_by_facet(SAMPLE_RESULTS, FACET_INSTAGRAM)
    assert len(ig_results) == 1
    assert ig_results[0]["save"]["platform"] == "instagram"

    # 3. All facet
    all_results = filter_results_by_facet(SAMPLE_RESULTS, FACET_ALL)
    assert len(all_results) == 2


def test_search_view_error_state_and_retry():
    """Verify error banner and retry callback behavior on failure."""
    calls = []

    def failing_search(q: str, s: str | None, c: str | None):
        calls.append(q)
        raise RuntimeError("Network timeout")

    view = SearchView(on_search=failing_search)
    view.submit_search("pasta")

    assert view.error_banner.visible is True
    assert "Search failed: Network timeout" in view.error_text.value
    assert len(calls) == 1

    # Trigger Retry
    click_fn: Any = view.retry_button.on_click
    assert callable(click_fn)
    click_fn(None)
    assert len(calls) == 2

