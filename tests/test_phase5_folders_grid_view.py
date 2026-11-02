"""Unit tests for FoldersGridView (Phase 5 deliverable P5-04)."""

from typing import Any
import flet as ft
import pytest

from app.views.folders.folder_card import FolderCard
from app.views.folders.folders_grid_view import (
    SORT_ALPHA,
    SORT_RECENT,
    SORT_SAVES,
    FoldersGridView,
    sort_folders,
)

SAMPLE_FOLDERS = [
    {
        "id": "018f4c1a-0000-7de6-9c8e-000000000004",
        "parent_id": None,
        "name": "Cooking",
        "save_count": 24,
        "updated_at": "2026-10-31T12:00:00Z",
    },
    {
        "id": "018f4c1a-0000-7de6-9c8e-000000000006",
        "parent_id": None,
        "name": "Fitness",
        "save_count": 13,
        "updated_at": "2026-10-30T10:00:00Z",
    },
    {
        "id": "018f4c1a-0000-7de6-9c8e-000000000007",
        "parent_id": None,
        "name": "Art",
        "save_count": 35,
        "updated_at": "2026-10-28T08:00:00Z",
    },
]


def test_sort_folders_strategies():
    """Verify all 3 sorting algorithms produce correct orderings."""
    # Alpha sort
    by_alpha = sort_folders(SAMPLE_FOLDERS, SORT_ALPHA)
    names_alpha = [f["name"] for f in by_alpha]
    assert names_alpha == ["Art", "Cooking", "Fitness"]

    # Saves sort
    by_saves = sort_folders(SAMPLE_FOLDERS, SORT_SAVES)
    names_saves = [f["name"] for f in by_saves]
    assert names_saves == ["Art", "Cooking", "Fitness"]  # 35, 24, 13

    # Recent sort
    by_recent = sort_folders(SAMPLE_FOLDERS, SORT_RECENT)
    names_recent = [f["name"] for f in by_recent]
    assert names_recent == ["Cooking", "Fitness", "Art"]


def test_folders_grid_view_empty_state():
    """Verify empty state is shown when no folders are provided."""
    grid_view = FoldersGridView(folders=[])

    assert len(grid_view.grid_column.controls) == 1
    empty_container = grid_view.grid_column.controls[0]
    assert isinstance(empty_container, ft.Container)
    # Check that text mentions project prompt
    col = empty_container.content
    assert isinstance(col, ft.Column)
    texts = [c.value for c in col.controls if isinstance(c, ft.Text)]
    assert "No folders yet" in texts
    assert any("Folders are for projects" in (t or "") for t in texts)


def test_folders_grid_view_2_column_layout():
    """Verify 2-column paired rows are created for odd and even counts."""
    # 3 folders -> 2 rows (row 0 has 2 cards, row 1 has 1 card + 1 spacer)
    grid_view = FoldersGridView(folders=SAMPLE_FOLDERS)

    rows = grid_view.grid_column.controls
    assert len(rows) == 2

    row_0 = rows[0]
    assert isinstance(row_0, ft.Row)
    assert len(row_0.controls) == 2
    cell_0_0 = row_0.controls[0]
    cell_0_1 = row_0.controls[1]
    assert isinstance(cell_0_0, ft.Container)
    assert isinstance(cell_0_1, ft.Container)
    assert isinstance(cell_0_0.content, FolderCard)
    assert isinstance(cell_0_1.content, FolderCard)

    row_1 = rows[1]
    assert isinstance(row_1, ft.Row)
    assert len(row_1.controls) == 2
    cell_1_0 = row_1.controls[0]
    cell_1_1 = row_1.controls[1]
    assert isinstance(cell_1_0, ft.Container)
    assert isinstance(cell_1_1, ft.Container)
    assert isinstance(cell_1_0.content, FolderCard)
    # The spacer is an empty container with expand=1
    assert cell_1_1.content is None


def test_folders_grid_view_new_folder_action():
    """Verify + New folder button invokes callback."""
    actions = []

    grid_view = FoldersGridView(
        folders=SAMPLE_FOLDERS,
        on_new_folder=lambda: actions.append("new"),
    )

    click_fn: Any = grid_view.new_button.on_click
    assert callable(click_fn)
    click_fn(None)
    assert actions == ["new"]


def test_folders_grid_view_sorting_interaction():
    """Verify clicking sort chips re-sorts the rendered items."""
    grid_view = FoldersGridView(folders=SAMPLE_FOLDERS)
    assert grid_view.active_sort == SORT_RECENT

    # Switch to A to Z
    grid_view._set_sort(SORT_ALPHA)
    assert grid_view.active_sort == SORT_ALPHA

    first_row = grid_view.grid_column.controls[0]
    assert isinstance(first_row, ft.Row)
    cell = first_row.controls[0]
    assert isinstance(cell, ft.Container)
    first_card = cell.content
    assert isinstance(first_card, FolderCard)
    assert first_card.folder_name == "Art"


def test_folders_grid_view_set_folders():
    """Verify set_folders dynamically updates the view."""
    grid_view = FoldersGridView(folders=[])
    assert len(grid_view._raw_folders) == 0

    grid_view.set_folders(SAMPLE_FOLDERS)
    assert len(grid_view._raw_folders) == 3
    assert len(grid_view.grid_column.controls) == 2

