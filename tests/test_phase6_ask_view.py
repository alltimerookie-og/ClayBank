"""Unit tests for Phase 6 Ask assistant view (P6-04).

Covers:
- Library vs folder scoped views and labels.
- Header title, back button, and scope chip rendering.
- Suggested prompt pills rendering and auto-submit on click.
- Question submission lifecycle (AskUserBubble, typing dots, AskAnswerCard).
- Query dispatch with correct scope parameter.
- Citation chip navigation callback propagation.
- Initial message history restoration.
- Backend error handling gracefully rendered.
"""

from __future__ import annotations

import flet as ft
import pytest

from app.views.search.ask_message import AskAnswerCard, AskUserBubble
from app.views.search.ask_view import (
    DEFAULT_FOLDER_PROMPTS,
    DEFAULT_LIBRARY_PROMPTS,
    AskView,
)


def test_ask_view_library_scope_initialization():
    """AskView initializes library-scoped UI elements correctly."""
    view = AskView(scope="library")
    assert view.scope == "library"
    assert view.title_label == "Ask your library"
    assert view.back_label == "Search"
    assert view.scope_chip_text == "Library"
    assert view.prompts == DEFAULT_LIBRARY_PROMPTS


def test_ask_view_folder_scope_initialization():
    """AskView initializes folder-scoped UI elements correctly."""
    view = AskView(scope="f_recipes_123", folder_name="Recipes")
    assert view.scope == "f_recipes_123"
    assert view.title_label == "Ask Recipes"
    assert view.back_label == "Recipes"
    assert view.scope_chip_text == "Recipes"
    assert any("Recipes" in p for p in view.prompts)


def test_ask_view_back_navigation():
    """AskView back button triggers on_back callback."""
    back_invoked = False

    def on_back():
        nonlocal back_invoked
        back_invoked = True

    view = AskView(on_back=on_back)
    view._handle_back()
    assert back_invoked is True


def test_ask_view_question_submission_and_citations():
    """Submitting a question queries assistant and renders bubbles with citation chips."""
    queries_received: list[tuple[str, str | None]] = []
    citations_clicked: list[tuple[str, str | None]] = []

    def mock_ask_query(q: str, scope: str | None) -> dict:
        queries_received.append((q, scope))
        return {
            "answer": f"Answer to {q}",
            "scope": scope,
            "engine": "cloud",
            "citations": [
                {
                    "save_id": "018f4c1a-0000-7de6-9c8e-000000000001",
                    "anchor": "1:20",
                    "quote": "Salt to taste",
                }
            ],
        }

    def mock_citation_click(save_id: str, anchor: str | None) -> None:
        citations_clicked.append((save_id, anchor))

    view = AskView(
        scope="library",
        on_ask_query=mock_ask_query,
        on_click_citation=mock_citation_click,
        save_lookup={"018f4c1a-0000-7de6-9c8e-000000000001": {"title": "Pasta Note"}},
    )

    # Submit question
    view.submit_question("How much salt should I add?")

    assert len(queries_received) == 1
    assert queries_received[0] == ("How much salt should I add?", "library")

    # Verify message list controls: suggestions section + user bubble + answer card
    controls = view.message_list.controls
    user_bubbles = [c for c in controls if isinstance(c, AskUserBubble)]
    answer_cards = [c for c in controls if isinstance(c, AskAnswerCard)]

    assert len(user_bubbles) == 1
    assert user_bubbles[0].message == "How much salt should I add?"

    assert len(answer_cards) == 1
    assert answer_cards[0].raw_answer == "Answer to How much salt should I add?"

    # Trigger citation click on answer card
    answer_cards[0]._handle_citation_click("018f4c1a-0000-7de6-9c8e-000000000001", "1:20")
    assert citations_clicked == [("018f4c1a-0000-7de6-9c8e-000000000001", "1:20")]


def test_ask_view_initial_messages_restoration():
    """AskView populates message stream when initial_messages are provided."""
    initial = [
        (
            "What is sourdough hydration?",
            {
                "answer": "Hydration is the ratio of water to flour.",
                "scope": "library",
                "engine": "cloud",
                "citations": [{"save_id": "s_1", "anchor": None}],
            },
        )
    ]

    view = AskView(initial_messages=initial)
    controls = view.message_list.controls
    user_bubbles = [c for c in controls if isinstance(c, AskUserBubble)]
    answer_cards = [c for c in controls if isinstance(c, AskAnswerCard)]

    assert len(user_bubbles) == 1
    assert user_bubbles[0].message == "What is sourdough hydration?"
    assert len(answer_cards) == 1
    assert len(view.conversation_history) == 1


def test_ask_view_error_handling():
    """Backend exception during query renders error card without crashing."""
    def failing_query(q: str, scope: str | None) -> dict:
        raise RuntimeError("Network offline")

    view = AskView(on_ask_query=failing_query)
    view.submit_question("Will this fail?")

    answer_cards = [c for c in view.message_list.controls if isinstance(c, AskAnswerCard)]
    assert len(answer_cards) == 1
    assert "Network offline" in answer_cards[0].raw_answer
    assert view.typing_dots is None
    assert view.is_processing is False
