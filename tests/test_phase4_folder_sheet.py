"""Unit tests for P4-07: Folder Filing Sheet."""

from __future__ import annotations

import flet as ft

from app.views.note.folder_sheet import FolderFilingSheet


def test_folder_sheet_initial_render() -> None:
    """Verify sheet initializes with folder chips and current folder highlighted."""
    sheet = FolderFilingSheet(
        current_folder="Cooking / Pasta",
        available_folders=["Cooking / Pasta", "Fitness", "Study"],
    )

    assert sheet.selected_folder == "Cooking / Pasta"
    # Controls: Inbox (Unfiled) + 3 folders = 4 chips
    assert len(sheet.folders_wrap.controls) == 4


def test_folder_sheet_search_filtering() -> None:
    """Verify search filter reduces visible folders."""
    sheet = FolderFilingSheet(
        available_folders=["Cooking / Pasta", "Cooking / Baking", "Fitness", "Study"],
    )

    sheet.search_field.value = "cook"
    sheet._handle_search_change(None)

    # Inbox (always present) + 2 Cooking folders = 3 chips
    assert len(sheet.folders_wrap.controls) == 3


def test_folder_sheet_select_folder_and_done() -> None:
    """Verify selecting a folder and clicking Done emits the folder path."""
    selected_result: str | None = "initial"

    def on_done(path: str | None) -> None:
        nonlocal selected_result
        selected_result = path

    sheet = FolderFilingSheet(
        current_folder="Study",
        available_folders=["Cooking / Pasta", "Fitness", "Study"],
        on_select_folder=on_done,
    )

    # Select 'Fitness'
    sheet._select_path("Fitness")
    assert sheet.selected_folder == "Fitness"

    # Click Done
    sheet.done()
    assert selected_result == "Fitness"


def test_folder_sheet_select_inbox_unfiled() -> None:
    """Verify selecting Inbox unfiles the save and returns None."""
    selected_result: str | None = "initial"

    def on_done(path: str | None) -> None:
        nonlocal selected_result
        selected_result = path

    sheet = FolderFilingSheet(
        current_folder="Study",
        on_select_folder=on_done,
    )

    sheet._select_path(None)
    assert sheet.selected_folder is None

    sheet.done()
    assert selected_result is None


def test_folder_sheet_cancel_callback() -> None:
    """Verify cancel button invokes on_cancel callback."""
    cancelled = False

    def on_cancel() -> None:
        nonlocal cancelled
        cancelled = True

    sheet = FolderFilingSheet(on_cancel=on_cancel)
    sheet.cancel()
    assert cancelled


def test_folder_sheet_dark_theme() -> None:
    """Verify dark mode initialization."""
    sheet = FolderFilingSheet(theme_mode=ft.ThemeMode.DARK)
    assert sheet.theme_mode_val == ft.ThemeMode.DARK

