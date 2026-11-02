"""Unit tests for FolderDetailView (Phase 5 deliverable P5-05)."""

from typing import Any
import flet as ft
import pytest

from app.ui.chips import FolderChip, TagChip
from app.views.folders.folder_detail_view import FolderDetailView, FolderSaveCard

SAMPLE_FOLDER = {
    "id": "018f4c1a-0000-7de6-9c8e-000000000004",
    "name": "Cooking",
    "save_count": 24,
}

SAMPLE_SUBFOLDERS = [
    {
        "id": "018f4c1a-0000-7de6-9c8e-000000000005",
        "parent_id": "018f4c1a-0000-7de6-9c8e-000000000004",
        "name": "Pasta",
        "save_count": 6,
    },
    {
        "id": "018f4c1a-0000-7de6-9c8e-000000000008",
        "parent_id": "018f4c1a-0000-7de6-9c8e-000000000004",
        "name": "Baking",
        "save_count": 4,
    },
]

SAMPLE_SAVES = [
    {
        "id": "018f4c1a-0000-7de6-9c8e-000000000001",
        "title": "Creamy Garlic Pasta",
        "platform": "instagram",
        "tags": ["pasta", "recipe", "dinner"],
    },
    {
        "id": "018f4c1a-0000-7de6-9c8e-000000000002",
        "title": "Sourdough Bread Guide",
        "platform": "youtube",
        "tags": ["baking", "bread"],
    },
    {
        "id": "018f4c1a-0000-7de6-9c8e-000000000003",
        "title": "Classic Tomato Sauce",
        "platform": "web",
        "tags": ["pasta", "sauces"],
    },
]


def test_folder_detail_view_header_and_breadcrumbs():
    """Verify back button, breadcrumbs, title, and count."""
    back_invoked = []

    view = FolderDetailView(
        folder_data=SAMPLE_FOLDER,
        saves=SAMPLE_SAVES,
        breadcrumb_trail=[("c_id", "Cooking")],
        on_back=lambda: back_invoked.append(True),
    )

    assert view.title_text.value == "Cooking"
    assert "3 saves" in view.count_text.value
    assert "Folders / Cooking" in view.breadcrumb_text.value

    back_fn: Any = view.back_button.on_click
    assert callable(back_fn)
    back_fn(None)
    assert len(back_invoked) == 1


def test_folder_detail_view_subfolders_row_navigate():
    """Verify subfolder chips trigger on_select_subfolder (Verb: Navigate)."""
    selected_subfolders = []

    view = FolderDetailView(
        folder_data=SAMPLE_FOLDER,
        subfolders=SAMPLE_SUBFOLDERS,
        saves=SAMPLE_SAVES,
        on_select_subfolder=lambda sf: selected_subfolders.append(sf),
    )

    assert view.folders_section.visible is True
    chip_row = view.folders_section.controls[1]
    assert isinstance(chip_row, ft.Row)

    # First subfolder chip is Pasta (chevron=True)
    pasta_chip = chip_row.controls[0]
    assert isinstance(pasta_chip, FolderChip)
    assert pasta_chip.chip_path == "Pasta"
    assert pasta_chip.chevron is True

    click_fn: Any = pasta_chip.on_click
    assert callable(click_fn)
    click_fn(None)
    assert len(selected_subfolders) == 1
    assert selected_subfolders[0]["name"] == "Pasta"


def test_folder_detail_view_tags_row_filter_in_place():
    """Verify clicking tag chips filters saves stream in-place (Verb: Filter in place)."""
    view = FolderDetailView(
        folder_data=SAMPLE_FOLDER,
        subfolders=SAMPLE_SUBFOLDERS,
        saves=SAMPLE_SAVES,
    )

    # Initially all 3 saves are displayed
    assert len(view.saves_column.controls) == 3

    # Filter by pasta
    view._set_tag_filter("pasta")
    assert view.selected_tag == "pasta"
    # Pasta is in Creamy Garlic Pasta and Classic Tomato Sauce (2 saves)
    assert len(view.saves_column.controls) == 2
    titles: list[str] = []
    for c in view.saves_column.controls:
        if isinstance(c, FolderSaveCard):
            titles.append(c.save_item["title"])
    assert titles == ["Creamy Garlic Pasta", "Classic Tomato Sauce"]

    # Filter by baking (1 save)
    view._set_tag_filter("baking")
    assert len(view.saves_column.controls) == 1
    first_item = view.saves_column.controls[0]
    assert isinstance(first_item, FolderSaveCard)
    assert first_item.save_item["title"] == "Sourdough Bread Guide"

    # Reset filter
    view._set_tag_filter(None)
    assert len(view.saves_column.controls) == 3


def test_folder_detail_view_save_click():
    """Verify tapping a save card invokes on_select_save."""
    clicked_saves = []

    view = FolderDetailView(
        folder_data=SAMPLE_FOLDER,
        saves=SAMPLE_SAVES,
        on_select_save=lambda s: clicked_saves.append(s),
    )

    first_card = view.saves_column.controls[0]
    assert isinstance(first_card, FolderSaveCard)
    assert callable(first_card.on_click_callback)
    first_card.on_click_callback(first_card.save_item)

    assert len(clicked_saves) == 1
    assert clicked_saves[0]["title"] == "Creamy Garlic Pasta"


def test_folder_detail_view_depth_limit_actions():
    """Verify depth limit disables subfolder creation at depth 3."""
    view_depth_3 = FolderDetailView(
        folder_data={"id": "f3", "name": "Deep"},
        folder_depth=3,
    )
    def extract_menu_labels(menu):
        labels = []
        for item in menu.items:
            if isinstance(item, ft.PopupMenuItem) and isinstance(item.content, ft.Row):
                for ctrl in item.content.controls:
                    if isinstance(ctrl, ft.Text):
                        labels.append(ctrl.value)
        return labels

    menu_labels_3 = extract_menu_labels(view_depth_3.overflow_menu)
    assert "Add subfolder" not in menu_labels_3

    view_depth_1 = FolderDetailView(
        folder_data={"id": "f1", "name": "Top"},
        folder_depth=1,
    )
    menu_labels_1 = extract_menu_labels(view_depth_1.overflow_menu)
    assert "Add subfolder" in menu_labels_1
