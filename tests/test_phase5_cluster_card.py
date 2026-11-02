"""Unit tests for ClusterSuggestionCard component (Phase 5 deliverable P5-06)."""

import flet as ft
import pytest

from app.views.folders.cluster_card import ClusterSuggestionCard

SAMPLE_CLUSTER_SUGGESTION = {
    "type": "cluster",
    "save_id": None,
    "cluster": [
        {
            "save_id": "018f4c1a-0000-7de6-9c8e-000000000001",
            "title": "Creamy garlic pasta",
        },
        {
            "save_id": "018f4c1a-0000-7de6-9c8e-000000000002",
            "title": "One pot pasta",
        },
        {
            "save_id": "018f4c1a-0000-7de6-9c8e-000000000008",
            "title": "Sauce basics",
        },
    ],
    "path": "Cooking",
    "confidence": 0.88,
    "dismissed_at": None,
    "accepted": False,
}


def test_cluster_suggestion_card_render():
    """Verify card displays cluster previews, path, and confidence score."""
    card = ClusterSuggestionCard(SAMPLE_CLUSTER_SUGGESTION)

    assert card.target_path == "Cooking"
    assert card.confidence_val == 0.88
    assert len(card.cluster_items) == 3
    assert not card.is_accepted

    col = card.main_container
    assert isinstance(col, ft.Column)
    # Header should contain 88% match
    header_row = col.controls[0]
    assert isinstance(header_row, ft.Row)
    texts = [ctrl.value for ctrl in header_row.controls if isinstance(ctrl, ft.Text)]
    assert "88% match" in texts or any("88%" in (t or "") for t in texts)


def test_cluster_suggestion_card_accept():
    """Verify accept builds suggestion-accept payload and transitions to undo state."""
    accepted_payloads = []

    def on_accept(payload):
        accepted_payloads.append(payload)

    card = ClusterSuggestionCard(
        SAMPLE_CLUSTER_SUGGESTION,
        on_accept=on_accept,
    )

    card.accept()

    assert card.is_accepted
    assert len(accepted_payloads) == 1
    p = accepted_payloads[0]
    assert p["type"] == "cluster"
    assert p["accept"] is True
    assert p["path"] == "Cooking"
    assert len(p["cluster"]) == 3

    # Check that card content now displays undo banner
    row = card.main_container.controls[0]
    assert isinstance(row, ft.Row)
    undo_buttons = [c for c in row.controls if isinstance(c, ft.TextButton)]
    assert len(undo_buttons) == 1
    assert undo_buttons[0].content == "Undo"


def test_cluster_suggestion_card_ignore():
    """Verify ignore builds dismissal payload with dismissed_at timestamp."""
    ignored_payloads = []

    def on_ignore(payload):
        ignored_payloads.append(payload)

    card = ClusterSuggestionCard(
        SAMPLE_CLUSTER_SUGGESTION,
        on_ignore=on_ignore,
    )

    card.ignore()

    assert card.is_dismissed is True
    assert card.visible is False
    assert len(ignored_payloads) == 1
    p = ignored_payloads[0]
    assert p["type"] == "cluster"
    assert p["accept"] is False
    assert "dismissed_at" in p
    assert p["dismissed_at"] is not None


def test_cluster_suggestion_card_undo():
    """Verify undo reverts the accepted state."""
    undone_payloads = []

    def on_undo(payload):
        undone_payloads.append(payload)

    card = ClusterSuggestionCard(
        SAMPLE_CLUSTER_SUGGESTION,
        on_undo=on_undo,
    )

    card.accept()
    assert card.is_accepted

    card.undo()
    assert not card.is_accepted
    assert len(undone_payloads) == 1
    assert undone_payloads[0]["accept"] is False
