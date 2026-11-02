"""Unit tests for FolderCard component (Phase 5 deliverable P5-02)."""

from typing import Any
import flet as ft
import pytest

from app.views.folders.folder_card import FolderCard, format_folder_subtitle
from app.views.folders.folder_collage import FolderCoverCollage


def test_format_folder_subtitle_with_count_and_recency():
    """Verify subtitle formats with both count and recency."""
    assert format_folder_subtitle(24, recency="today") == "24 saves · today"
    assert format_folder_subtitle(1, recency="yesterday") == "1 save · yesterday"


def test_format_folder_subtitle_hides_zero_count():
    """Verify save count is hidden when zero or negative (Docs/UIUX.md §7)."""
    assert format_folder_subtitle(0, recency="today") == "today"
    assert format_folder_subtitle(0) == ""
    assert format_folder_subtitle(-5, recency="2d ago") == "2d ago"
    assert format_folder_subtitle(None) == ""


def test_folder_card_renders_fixture_data():
    """Verify FolderCard creates correct title, subtitle, and collage."""
    folder_data = {
        "id": "018f4c1a-0000-7de6-9c8e-000000000004",
        "parent_id": None,
        "name": "Cooking",
        "save_count": 24,
        "updated_at": "2026-10-31T12:00:00Z",
    }

    card = FolderCard(folder_data, recency="today")

    assert card.folder_id == folder_data["id"]
    assert card.folder_name == "Cooking"
    assert card.title_control.value == "Cooking"
    assert card.subtitle_control is not None
    assert card.subtitle_control.value == "24 saves · today"
    assert isinstance(card.collage, FolderCoverCollage)


def test_folder_card_empty_folder_hides_count():
    """Verify empty folder does not display '0 saves'."""
    folder_data = {
        "id": "018f4c1a-0000-7de6-9c8e-000000000099",
        "name": "Empty Project",
        "save_count": 0,
    }

    card = FolderCard(folder_data)
    assert card.subtitle_control is None
    assert card.subtitle_text == ""


def test_folder_card_click_callback():
    """Verify on_click callback triggers when tapped."""
    clicked_data = []

    def on_click(data):
        clicked_data.append(data)

    folder_data = {
        "id": "018f4c1a-0000-7de6-9c8e-000000000004",
        "name": "Cooking",
        "save_count": 24,
    }

    card = FolderCard(folder_data, on_click=on_click)
    # Simulate container click
    click_fn: Any = card.on_click
    assert callable(click_fn)
    click_fn(None)

    assert len(clicked_data) == 1
    assert clicked_data[0]["name"] == "Cooking"


def test_folder_card_long_press_callback():
    """Verify on_long_press callback triggers for context actions."""
    long_pressed = []

    def on_long_press(data):
        long_pressed.append(data)

    folder_data = {
        "id": "018f4c1a-0000-7de6-9c8e-000000000005",
        "name": "Pasta",
        "save_count": 6,
    }

    card = FolderCard(folder_data, on_long_press=on_long_press)
    long_press_fn: Any = card.on_long_press
    assert callable(long_press_fn)
    long_press_fn(None)

    assert len(long_pressed) == 1
    assert long_pressed[0]["name"] == "Pasta"


def test_folder_card_dark_theme_compatibility():
    """Verify FolderCard creates cleanly in dark theme mode."""
    folder_data = {
        "id": "018f4c1a-0000-7de6-9c8e-000000000004",
        "name": "Fitness",
        "save_count": 13,
    }
    card = FolderCard(folder_data, recency="2d ago", theme_mode=ft.ThemeMode.DARK)
    assert card.title_control.value == "Fitness"
    assert card.subtitle_control is not None
    assert card.subtitle_control.value == "13 saves · 2d ago"

