"""Unit tests for P2-06: Quick-Check Card."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from app.views.quick_check_card import QuickCheckCard

FIXTURES_PATH = Path("Docs/api/fixtures")


def test_quick_check_card_single_fixture() -> None:
    """Verify quick-check card binds correctly to single suggestion fixture."""
    fixtures = json.loads((FIXTURES_PATH / "suggestion.fixtures.json").read_text(encoding="utf-8"))
    single_sugg = fixtures["valid"][0]

    card = QuickCheckCard(
        single_sugg,
        title="Creamy garlic pasta",
        platform="instagram",
    )

    assert card.save_id == "018f4c1a-0000-7de6-9c8e-000000000001"
    assert card.target_path == "Cooking / Pasta"
    assert card.confidence_text.value == "94% match"
    assert card.title_text.value == "Creamy garlic pasta"
    assert card.platform_chip.platform == "instagram"


def test_quick_check_card_cluster_fixture() -> None:
    """Verify quick-check card handles cluster suggestion correctly."""
    fixtures = json.loads((FIXTURES_PATH / "suggestion.fixtures.json").read_text(encoding="utf-8"))
    cluster_sugg = fixtures["valid"][1]

    card = QuickCheckCard(
        cluster_sugg,
        platform="web",
    )

    assert card.suggestion_type == "cluster"
    assert card.title_text.value == "3 related items to organize"
    assert card.target_path == "Cooking"
    assert card.confidence_text.value == "88% match"


def test_quick_check_card_accept_action() -> None:
    """Verify Accept action invokes on_accept callback and updates state."""
    accepted_save_id = ""
    accepted_folder = ""

    def on_acc(s_id: str, f_path: str) -> None:
        nonlocal accepted_save_id, accepted_folder
        accepted_save_id = s_id
        accepted_folder = f_path

    card = QuickCheckCard(
        {
            "save_id": "save-123",
            "path": "Research / AI",
            "confidence": 0.91,
        },
        on_accept=on_acc,
    )

    card.accept()
    assert card.is_accepted is True
    assert accepted_save_id == "save-123"
    assert accepted_folder == "Research / AI"
    assert "Moved to Research / AI" in card.status_feedback.value
    assert card.accept_button.disabled is True
    assert card.ignore_button.disabled is True


def test_quick_check_card_ignore_action() -> None:
    """Verify Ignore action invokes on_ignore callback and preserves inbox status."""
    ignored_id = ""

    def on_ign(s_id: str) -> None:
        nonlocal ignored_id
        ignored_id = s_id

    card = QuickCheckCard(
        {
            "save_id": "save-456",
            "path": "Reading",
            "confidence": 0.75,
        },
        on_ignore=on_ign,
    )

    card.ignore()
    assert card.is_ignored is True
    assert ignored_id == "save-456"
    assert card.status_feedback.value == "Suggestion dismissed"
    assert card.accept_button.disabled is True


def test_quick_check_card_undo_reversal() -> None:
    """Verify undo action reverses accept/ignore state and re-enables controls."""
    undo_invoked = False

    def on_un() -> None:
        nonlocal undo_invoked
        undo_invoked = True

    card = QuickCheckCard(
        {
            "save_id": "save-789",
            "path": "Recipes",
            "confidence": 0.85,
        },
        on_undo=on_un,
    )

    card.accept()
    assert card.is_accepted

    card.undo_action()
    assert not card.is_accepted
    assert not card.is_ignored
    assert not card.accept_button.disabled
    assert not card.status_feedback.visible
    assert undo_invoked


def test_quick_check_card_choose_folder_trigger() -> None:
    """Verify tapping folder chip triggers folder picker callback."""
    chosen_id = ""

    def on_choose(s_id: str) -> None:
        nonlocal chosen_id
        chosen_id = s_id

    card = QuickCheckCard(
        {
            "save_id": "save-folder-test",
            "path": "Tech",
            "confidence": 0.90,
        },
        on_choose_folder=on_choose,
    )

    card.choose_folder()
    assert chosen_id == "save-folder-test"

