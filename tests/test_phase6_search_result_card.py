"""Unit tests for SearchResultCard component (Phase 6 deliverable P6-01)."""

from typing import Any
import flet as ft
import pytest

from app.views.search.search_result_card import (
    SearchResultCard,
    format_match_reason,
)


def test_format_match_reason_variants():
    """Verify match reason formatting for known and unknown reasons."""
    assert format_match_reason("transcript") == "Match in transcript"
    assert format_match_reason("title") == "Match in title"
    assert format_match_reason("body") == "Match in body"
    assert format_match_reason("tag") == "Match in tag"
    assert format_match_reason("folder") == "Match in folder"
    assert format_match_reason("semantic") == "Match by meaning"
    assert format_match_reason("custom_section") == "Match in custom_section"
    assert format_match_reason(None) == "Match found"


def test_search_result_card_render_transcript_match():
    """Verify rendering of card with transcript match, fragment, and jump target."""
    result = {
        "save": {
            "id": "018f4c1a-0000-7de6-9c8e-000000000001",
            "url": "https://www.instagram.com/reel/Cx9abc/",
            "platform": "instagram",
            "title": "Creamy garlic pasta",
            "folder": "Cooking / Pasta",
            "kind": "video",
        },
        "match_reason": "transcript",
        "fragment": "add cream at the end",
        "jump_target": "0:42",
        "score": 0.98,
    }

    card = SearchResultCard(result)

    assert card.save_id == "018f4c1a-0000-7de6-9c8e-000000000001"
    assert card.title_text.value == "Creamy garlic pasta"
    assert card.jump_target == "0:42"
    assert card.score == 0.98

    # Verify card content structure
    content = card.content
    assert isinstance(content, ft.Row)
    assert len(content.controls) == 2
    thumbnail, info_col = content.controls[0], content.controls[1]
    assert isinstance(thumbnail, ft.Container)
    assert isinstance(info_col, ft.Column)


def test_search_result_card_semantic_match_without_fragment():
    """Verify rendering of semantic match with null fragment and jump target."""
    result = {
        "save": {
            "id": "018f4c1a-0000-7de6-9c8e-000000000003",
            "url": "https://example.com/posts/sous-vide",
            "platform": "web",
            "user_context": "Sous vide cooking guide",
            "kind": "article",
        },
        "match_reason": "semantic",
        "fragment": None,
        "jump_target": None,
        "score": 0.76,
    }

    card = SearchResultCard(result)
    assert card.title_text.value == "Sous vide cooking guide"
    assert card.jump_target is None


def test_search_result_card_click_callback():
    """Verify tapping card invokes on_click callback with save data."""
    clicked: list[dict[str, Any]] = []
    result = {
        "save": {
            "id": "018f4c1a-0000-7de6-9c8e-000000000002",
            "title": "One pot pasta",
            "platform": "youtube",
        },
        "match_reason": "title",
        "score": 0.85,
    }

    card = SearchResultCard(
        result,
        on_click=lambda s: clicked.append(s),
    )

    card._handle_card_click()
    assert len(clicked) == 1
    assert clicked[0]["title"] == "One pot pasta"


def test_search_result_card_jump_callback():
    """Verify tapping jump target chip invokes on_jump with save and exact offset."""
    jumps: list[tuple[dict[str, Any], str]] = []
    result = {
        "save": {
            "id": "018f4c1a-0000-7de6-9c8e-000000000001",
            "title": "Creamy garlic pasta",
        },
        "match_reason": "transcript",
        "jump_target": "0:42",
        "score": 0.98,
    }

    card = SearchResultCard(
        result,
        on_jump=lambda s, target: jumps.append((s, target)),
    )

    card._handle_jump()
    assert len(jumps) == 1
    assert jumps[0][0]["id"] == "018f4c1a-0000-7de6-9c8e-000000000001"
    assert jumps[0][1] == "0:42"


def test_search_result_card_dark_theme_and_fallbacks():
    """Verify card handles dark theme and missing optional fields safely."""
    # Completely empty save dict
    result = {
        "save": {},
        "match_reason": "unknown_reason",
    }

    card = SearchResultCard(result, theme_mode=ft.ThemeMode.DARK)
    assert card.title_text.value == "Untitled Save"
    assert card.jump_target is None
    assert card.score is None
