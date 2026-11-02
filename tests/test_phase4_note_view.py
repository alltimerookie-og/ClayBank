"""Unit tests for P4-10: Item Note View Shell."""

from __future__ import annotations

import flet as ft

from app.views.note.note_view import ItemNoteView

RAW_NOTE_MARKDOWN = """---
source: Instagram
channel: @chefmara
video_url: https://instagram.com/reel/123
duration: 58
published: 2026-10-03
saved: 2026-10-31
folder: Cooking / Pasta
tags:
  - recipe
  - pasta
---
# Creamy garlic pasta

## Overview
A 20 minute pasta with garlic cream sauce.

## Key points
- Salt the water
- Fry garlic

## Transcript
> 0:08 Start with water.
> 0:42 Add cream.
"""


def test_note_view_initial_display_mode() -> None:
    """Verify default initial render in display mode."""
    view = ItemNoteView(
        save_id="save-001",
        raw_markdown=RAW_NOTE_MARKDOWN,
    )

    assert not view.is_editing
    assert view.display_mode_column.visible
    assert not view.edit_mode_container.visible
    assert view.header.folder_path_val == "Cooking / Pasta"
    assert view.bottom_button.content == "Open original video"


def test_note_view_toggle_edit_mode_and_flush() -> None:
    """Verify toggling to edit mode and returning flushes edits and updates views."""
    saved_markdowns: list[str] = []

    def on_save(save_id: str, content: str, updated_at: str) -> None:
        saved_markdowns.append(content)

    view = ItemNoteView(
        save_id="save-001",
        raw_markdown=RAW_NOTE_MARKDOWN,
        on_save_note=on_save,
    )

    # 1. Switch to edit mode
    view.set_editing_mode(True)
    assert view.is_editing
    assert not view.display_mode_column.visible
    assert view.edit_mode_container.visible
    assert view.bottom_button.content == "Done"

    # Simulate edit
    edited_text = RAW_NOTE_MARKDOWN.replace("Cooking / Pasta", "Cooking / Baking")
    view.markdown_editor.text_field.value = edited_text
    view.markdown_editor._handle_text_changed(None)

    # 2. Exit edit mode via bottom button or header
    view._handle_bottom_action()
    assert not view.is_editing
    assert view.display_mode_column.visible
    assert not view.edit_mode_container.visible
    assert view.header.folder_path_val == "Cooking / Baking"
    assert view.frontmatter.get("folder") == "Cooking / Baking"


def test_note_view_move_folder_and_undo() -> None:
    """Verify folder move updates state, emits snackbar, and supports undo."""
    moved_folders: list[str | None] = []

    def on_move(save_id: str, folder: str | None) -> None:
        moved_folders.append(folder)

    view = ItemNoteView(
        save_id="save-001",
        raw_markdown=RAW_NOTE_MARKDOWN,
        on_move_folder=on_move,
    )

    # Move to 'Fitness'
    view._handle_folder_selected("Fitness")

    assert view.frontmatter.get("folder") == "Fitness"
    assert view.header.folder_path_val == "Fitness"
    assert moved_folders == ["Fitness"]
    assert view.last_snackbar is not None
    assert "Moved to Fitness" in view.last_snackbar.message_text
    assert view.last_snackbar.duration == 5000

    # Undo folder move
    view._revert_folder_move("Cooking / Pasta")
    assert view.frontmatter.get("folder") == "Cooking / Pasta"
    assert view.header.folder_path_val == "Cooking / Pasta"
    assert moved_folders == ["Fitness", "Cooking / Pasta"]


def test_note_view_update_tags_and_undo() -> None:
    """Verify tag changes update state, emit snackbar, and support undo."""
    updated_tags: list[list[str]] = []

    def on_tags(save_id: str, tags: list[str]) -> None:
        updated_tags.append(tags)

    view = ItemNoteView(
        save_id="save-001",
        raw_markdown=RAW_NOTE_MARKDOWN,
        on_update_tags=on_tags,
    )

    # Save new tags
    view._handle_tags_saved(["quick", "dinner"])

    assert view.frontmatter.get("tags") == ["quick", "dinner"]
    assert updated_tags == [["quick", "dinner"]]
    assert view.last_snackbar is not None
    assert "Tags saved" in view.last_snackbar.message_text

    # Undo tags update
    view._revert_tags_update(["recipe", "pasta"])
    assert view.frontmatter.get("tags") == ["recipe", "pasta"]
    assert updated_tags == [["quick", "dinner"], ["recipe", "pasta"]]


def test_note_view_reprocess_protects_note_body() -> None:
    """Verify reprocess invokes pipeline without mutating note body."""
    reprocessed_id: str | None = None

    def on_reproc(save_id: str) -> None:
        nonlocal reprocessed_id
        reprocessed_id = save_id

    view = ItemNoteView(
        save_id="save-001",
        raw_markdown=RAW_NOTE_MARKDOWN,
        on_reprocess=on_reproc,
    )

    view._handle_reprocess()

    assert reprocessed_id == "save-001"
    assert view.last_snackbar is not None
    assert "never touched" in view.last_snackbar.message_text
    assert "Creamy garlic pasta" in view.clean_body


def test_note_view_delete_and_undo_restore() -> None:
    """Verify deletion hides note content, triggers callback, and undo restores view."""
    deleted_id: str | None = None
    restored_id: str | None = None

    def on_del(save_id: str) -> None:
        nonlocal deleted_id
        deleted_id = save_id

    def on_rest(save_id: str) -> None:
        nonlocal restored_id
        restored_id = save_id

    view = ItemNoteView(
        save_id="save-001",
        raw_markdown=RAW_NOTE_MARKDOWN,
        on_delete=on_del,
        on_restore_delete=on_rest,
    )

    # Open delete confirm
    view.handle_menu_action("delete")
    assert view.delete_container.visible

    # Confirm delete
    view._handle_delete_confirmed()
    assert deleted_id == "save-001"
    assert not view.display_mode_column.visible
    assert not view.bottom_button.visible
    assert view.last_snackbar is not None
    assert "Note deleted" in view.last_snackbar.message_text

    # Revert via undo
    view._restore_deleted_note()
    assert restored_id == "save-001"
    assert view.display_mode_column.visible
    assert view.bottom_button.visible
    assert not view.delete_container.visible


def test_note_view_conflict_banner_recovery() -> None:
    """Verify conflict banner dismissal on keep local."""
    view = ItemNoteView(
        save_id="save-001",
        raw_markdown=RAW_NOTE_MARKDOWN,
    )

    view.is_conflict = True
    view.conflict_container.visible = True

    view._handle_keep_local()
    assert not view.conflict_container.visible
    assert not view.is_conflict


def test_note_view_dark_theme() -> None:
    """Verify dark mode initialization."""
    view = ItemNoteView(
        save_id="save-001",
        raw_markdown=RAW_NOTE_MARKDOWN,
        theme_mode=ft.ThemeMode.DARK,
    )
    assert view.theme_mode_val == ft.ThemeMode.DARK
