"""Unit tests for Phase 6 Ask message components (P6-03).

Covers:
- AskUserBubble rendering, right-alignment, and theme compatibility.
- AskTypingDots rendering and structure.
- AskAnswerCard Markdown answer rendering, citation chip integration,
  save metadata lookup, click callback dispatch, mandatory citation guard,
  and local engine slower hint.
"""

from __future__ import annotations

import flet as ft
import pytest

from app.views.search.ask_message import (
    AskAnswerCard,
    AskTypingDots,
    AskUserBubble,
)


def test_ask_user_bubble_rendering():
    """AskUserBubble renders question text and right alignment."""
    bubble = AskUserBubble("What did I save about sourdough hydration?")
    assert bubble.message == "What did I save about sourdough hydration?"
    assert bubble.alignment == ft.MainAxisAlignment.END

    # Content container contains the text control
    container = bubble.controls[1]
    assert isinstance(container, ft.Container)
    assert isinstance(container.content, ft.Text)
    assert container.content.value == "What did I save about sourdough hydration?"


def test_ask_typing_dots_rendering():
    """AskTypingDots renders 3 indicator dots inside a card container."""
    dots = AskTypingDots(theme_mode=ft.ThemeMode.DARK)
    assert dots.alignment == ft.MainAxisAlignment.START

    card = dots.controls[0]
    assert isinstance(card, ft.Container)
    row = card.content
    assert isinstance(row, ft.Row)
    assert len(row.controls) == 3


def test_ask_answer_card_with_citations_and_callbacks():
    """AskAnswerCard renders Markdown, citation chips, and calls navigation callback."""
    clicked: list[tuple[str, str | None]] = []

    def on_cite(save_id: str, anchor: str | None) -> None:
        clicked.append((save_id, anchor))

    answer_data = {
        "answer": "You saved a sourdough recipe with **75% hydration**.",
        "scope": "library",
        "engine": "cloud",
        "citations": [
            {
                "save_id": "save_sourdough_01",
                "anchor": "ingredients",
                "quote": "75% hydration dough",
            },
            {
                "save_id": "save_sourdough_02",
                "anchor": None,
                "quote": "Bake at 450F with steam",
            },
        ],
    }

    save_lookup = {
        "save_sourdough_01": {"title": "Tartine Sourdough Guide"},
    }

    card = AskAnswerCard(
        answer_data,
        on_click_citation=on_cite,
        save_lookup=save_lookup,
    )

    assert card.raw_answer.startswith("You saved a sourdough recipe")
    assert len(card.citations) == 2
    assert card.engine == "cloud"

    # Verify column controls
    col = card.content
    assert isinstance(col, ft.Column)
    # Check Markdown exists
    markdown_controls = [c for c in col.controls if isinstance(c, ft.Markdown)]
    assert len(markdown_controls) == 1
    assert markdown_controls[0].value == answer_data["answer"]

    # Check subtitle
    text_controls = [c for c in col.controls if isinstance(c, ft.Text)]
    assert any("Based on 2 saves" in t.value for t in text_controls)

    # Check chips row
    chips_rows = [c for c in col.controls if isinstance(c, ft.Row)]
    assert len(chips_rows) == 1
    chips = chips_rows[0].controls
    assert len(chips) == 2

    # Click first citation chip
    card._handle_citation_click("save_sourdough_01", "ingredients")
    assert clicked == [("save_sourdough_01", "ingredients")]


def test_ask_answer_card_missing_citations_guard():
    """AskAnswerCard shows a warning if an answer has no grounded citations."""
    answer_data = {
        "answer": "Hallucinated or citation-free answer.",
        "citations": [],
    }

    card = AskAnswerCard(answer_data)
    col = card.content
    assert isinstance(col, ft.Column)

    # Should contain warning text
    texts = [c for c in col.controls if isinstance(c, ft.Text)]
    assert any("no grounded citations" in t.value for t in texts)


def test_ask_answer_card_local_engine_slower_hint():
    """AskAnswerCard displays slower hint for on-device local engine."""
    cloud_card = AskAnswerCard(
        {
            "answer": "Cloud answer.",
            "engine": "cloud",
            "citations": [{"save_id": "s1", "anchor": None}],
        }
    )
    col_cloud = cloud_card.content
    assert isinstance(col_cloud, ft.Column)
    texts_cloud = [c for c in col_cloud.controls if isinstance(c, ft.Text)]
    assert not any("running on device" in t.value for t in texts_cloud)

    local_card = AskAnswerCard(
        {
            "answer": "Local answer.",
            "engine": "local",
            "citations": [{"save_id": "s1", "anchor": None}],
        }
    )
    col_local = local_card.content
    assert isinstance(col_local, ft.Column)
    texts_local = [c for c in col_local.controls if isinstance(c, ft.Text)]
    assert any("running on device · slower" in t.value for t in texts_local)
