"""Unit tests for P4-02: Note Header and Breadcrumbs."""

from __future__ import annotations

import flet as ft

from app.views.note.note_header import NoteHeader


def test_note_header_default_with_folder() -> None:
    """Verify header composition with a folder path."""
    header = NoteHeader(folder_path="Cooking / Pasta")

    assert header.folder_path_val == "Cooking / Pasta"
    assert not header.is_editing_val
    assert header.edit_button_text.value == "Edit"

    # Breadcrumbs contain Folders / Cooking / Pasta
    spans = header.breadcrumb_text.spans
    assert spans is not None
    span_texts = [s.text for s in spans]
    assert "Folders / " in span_texts
    assert "Cooking / " in span_texts
    assert "Pasta" in span_texts


def test_note_header_unfiled_shows_inbox() -> None:
    """Verify header without folder defaults to Inbox in breadcrumbs."""
    header = NoteHeader(folder_path=None)
    spans = header.breadcrumb_text.spans
    assert spans is not None
    assert spans[0].text == "Inbox"

    header_empty = NoteHeader(folder_path="")
    assert header_empty.breadcrumb_text.spans[0].text == "Inbox"


def test_note_header_back_callback() -> None:
    """Verify back button triggers callback."""
    invoked = False

    def on_back() -> None:
        nonlocal invoked
        invoked = True

    header = NoteHeader(on_back=on_back)
    header.trigger_back()
    assert invoked


def test_note_header_move_affordance() -> None:
    """Verify '↩ move' affordance triggers move callback."""
    invoked = False

    def on_move() -> None:
        nonlocal invoked
        invoked = True

    header = NoteHeader(on_move=on_move)
    header.trigger_move()
    assert invoked


def test_note_header_toggle_edit() -> None:
    """Verify clicking edit button toggles mode and updates button text."""
    states: list[bool] = []

    def on_toggle(state: bool) -> None:
        states.append(state)

    header = NoteHeader(is_editing=False, on_toggle_edit=on_toggle)
    assert header.edit_button_text.value == "Edit"

    # Toggle to edit mode
    header.toggle_edit()
    assert header.is_editing_val
    assert header.edit_button_text.value == "Done"
    assert states == [True]

    # Toggle back to display mode
    header.toggle_edit()
    assert not header.is_editing_val
    assert header.edit_button_text.value == "Edit"
    assert states == [True, False]


def test_note_header_overflow_menu_actions() -> None:
    """Verify overflow menu dispatches appropriate action tokens."""
    dispatched: list[str] = []

    def on_action(action: str) -> None:
        dispatched.append(action)

    header = NoteHeader(on_menu_action=on_action)
    assert len(header.overflow_menu.items) == 4

    header.trigger_menu_action("move")
    header.trigger_menu_action("tags")
    header.trigger_menu_action("reprocess")
    header.trigger_menu_action("delete")

    assert dispatched == ["move", "tags", "reprocess", "delete"]


def test_note_header_dynamic_folder_update() -> None:
    """Verify dynamic update of folder path."""
    header = NoteHeader(folder_path="Cooking / Pasta")
    header.set_folder_path("Fitness")

    assert header.folder_path_val == "Fitness"
    span_texts = [s.text for s in header.breadcrumb_text.spans]
    assert "Fitness" in span_texts


def test_note_header_touch_targets_and_theme() -> None:
    """Verify touch target standards and dark mode support."""
    header = NoteHeader(theme_mode=ft.ThemeMode.DARK)

    assert header.back_button.width == 44.0
    assert header.back_button.height == 44.0
    assert header.edit_button.height == 44.0

