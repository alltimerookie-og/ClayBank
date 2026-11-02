"""Unit tests for P4-08: Tag Editor Sheet."""

from __future__ import annotations

import flet as ft

from app.views.note.tag_sheet import TagEditorSheet


def test_tag_sheet_initial_render() -> None:
    """Verify sheet initializes with tags formatted as chips with delete affordance."""
    sheet = TagEditorSheet(current_tags=["#recipe", "pasta", "dinner"])

    assert sheet.tags_list == ["recipe", "pasta", "dinner"]
    assert len(sheet.tags_row.controls) == 3


def test_tag_sheet_add_tag_normalization() -> None:
    """Verify adding tag trims whitespace, removes leading hashtag, and clears field."""
    sheet = TagEditorSheet(current_tags=["recipe"])

    sheet.tag_input.value = "  #quick-meal  "
    sheet.add_tag()

    assert "quick-meal" in sheet.tags_list
    assert len(sheet.tags_list) == 2
    assert sheet.tag_input.value == ""


def test_tag_sheet_prevent_duplicate_tags() -> None:
    """Verify adding an existing tag is ignored."""
    sheet = TagEditorSheet(current_tags=["recipe", "pasta"])

    sheet.tag_input.value = "#recipe"
    sheet.add_tag()

    assert len(sheet.tags_list) == 2


def test_tag_sheet_remove_tag() -> None:
    """Verify removing a tag updates the list and rebuilds chips."""
    sheet = TagEditorSheet(current_tags=["recipe", "pasta"])

    sheet.remove_tag("recipe")

    assert sheet.tags_list == ["pasta"]
    assert len(sheet.tags_row.controls) == 1


def test_tag_sheet_empty_state() -> None:
    """Verify empty tags list renders empty state message."""
    sheet = TagEditorSheet(current_tags=[])

    assert len(sheet.tags_list) == 0
    assert len(sheet.tags_row.controls) == 1
    text_ctrl = sheet.tags_row.controls[0]
    assert isinstance(text_ctrl, ft.Text)
    assert "(No tags added)" in (text_ctrl.value or "")


def test_tag_sheet_done_callback() -> None:
    """Verify clicking Done passes updated tag list to callback."""
    saved_tags: list[str] | None = None

    def on_save(tags: list[str]) -> None:
        nonlocal saved_tags
        saved_tags = tags

    sheet = TagEditorSheet(
        current_tags=["recipe"],
        on_save_tags=on_save,
    )

    sheet.tag_input.value = "baking"
    sheet.add_tag()
    sheet.done()

    assert saved_tags == ["recipe", "baking"]


def test_tag_sheet_cancel_callback() -> None:
    """Verify cancel button invokes on_cancel callback."""
    cancelled = False

    def on_cancel() -> None:
        nonlocal cancelled
        cancelled = True

    sheet = TagEditorSheet(on_cancel=on_cancel)
    sheet.cancel()
    assert cancelled


def test_tag_sheet_dark_theme() -> None:
    """Verify dark mode initialization."""
    sheet = TagEditorSheet(theme_mode=ft.ThemeMode.DARK)
    assert sheet.theme_mode_val == ft.ThemeMode.DARK

