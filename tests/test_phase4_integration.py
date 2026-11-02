"""Integration tests for Phase 4: Application Coordinator Integration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import pytest

from app.app import ClayBankApp
from app.shell.nav import TAB_INBOX
from app.ui.snackbar import UndoSnackBar
from app.views.note.note_view import ItemNoteView

FIXTURE_NOTE_ID = "018f4c1a-0000-7de6-9c8e-000000000001"

MOCK_SAVE_ITEM = {
    "id": FIXTURE_NOTE_ID,
    "url": "https://www.instagram.com/reel/canonical_Cx9abc/",
    "title": "Creamy garlic pasta",
    "platform": "instagram",
    "source_app": "Instagram",
    "folder": "Cooking / Pasta",
    "tags": ["recipe", "pasta", "dinner"],
    "channel": "@chefmara",
    "status": "completed",
    "captured_at": "2026-10-31T12:00:00Z",
}

SAMPLE_NOTE_MARKDOWN = """---
source: Instagram
channel: @chefmara
video_url: https://instagram.com/reel/canonical_Cx9abc
duration: 58
published: "2026-10-03"
saved: "2026-10-31"
folder: Cooking / Pasta
tags:
  - recipe
  - pasta
  - dinner
---
# Creamy garlic pasta

## Overview
A 20 minute pasta with a garlic cream sauce. Five ingredients, one pan.

## Key points
- Salt the water well
- Fry garlic on low heat
- Add cream last, then pasta water

## Transcript (excerpt)
> 0:08 — Start with well salted water.
> 0:42 — Now add the cream.
"""


def test_app_navigates_to_item_note_on_inbox_save_select() -> None:
    """Verify selecting an Inbox save navigates to ItemNoteView with correct save ID and body."""
    app = ClayBankApp(
        has_seen_onboarding=True,
        saves=[MOCK_SAVE_ITEM],
        notes={FIXTURE_NOTE_ID: SAMPLE_NOTE_MARKDOWN},
    )
    app.splash_view.finish_warmup()

    # Initial view is AppShellLayout
    assert app.viewport.content is app.app_shell
    assert app.current_note_view is None

    # Trigger save selection via inbox
    app.open_note_view(MOCK_SAVE_ITEM)

    # Viewport is now ItemNoteView
    assert app.viewport.content is app.current_note_view
    assert isinstance(app.viewport.content, ItemNoteView)
    assert app.current_note_view.save_id == FIXTURE_NOTE_ID
    assert "Creamy garlic pasta" in app.current_note_view.clean_body
    assert app.current_note_view.frontmatter.get("folder") == "Cooking / Pasta"


def test_app_back_action_restores_shell_navigation_context() -> None:
    """Verify back button returns to the previous shell context without adding extra tabs."""
    app = ClayBankApp(
        has_seen_onboarding=True,
        saves=[MOCK_SAVE_ITEM],
        notes={FIXTURE_NOTE_ID: SAMPLE_NOTE_MARKDOWN},
    )
    app.splash_view.finish_warmup()

    # Navigate to note
    app.open_note_view(MOCK_SAVE_ITEM)
    assert app.viewport.content is app.current_note_view

    # Click Back in note header
    app.current_note_view.header.back_button.on_click(None)

    # Shell context restored
    assert app.viewport.content is app.app_shell
    assert app.current_note_view is None
    assert app.app_shell.selected_index == TAB_INBOX
    # Confirm 4 standard tabs preserved (no 5th tab added)
    assert len(app.app_shell.nav_bar.destinations) == 4


def test_app_open_note_with_timestamp_jump_target() -> None:
    """Verify opening note with timestamp jump target sets target on renderer."""
    app = ClayBankApp(
        has_seen_onboarding=True,
        saves=[MOCK_SAVE_ITEM],
        notes={FIXTURE_NOTE_ID: SAMPLE_NOTE_MARKDOWN},
    )
    app.splash_view.finish_warmup()

    note_view = app.open_note_view(MOCK_SAVE_ITEM, jump_target="0:42")
    assert note_view is not None
    assert note_view.jump_target_val == "0:42"
    assert note_view.markdown_renderer.jump_target_val == "0:42"


def test_app_retrieve_note_through_custom_resolver() -> None:
    """Verify retrieving note via injected use-case / API client interface."""
    resolved_id: str | None = None

    def mock_get_note(save_id: str) -> dict[str, Any]:
        nonlocal resolved_id
        resolved_id = save_id
        return {
            "save_id": save_id,
            "markdown": SAMPLE_NOTE_MARKDOWN,
            "overview": "Custom resolved overview",
        }

    app = ClayBankApp(
        has_seen_onboarding=True,
        saves=[MOCK_SAVE_ITEM],
        on_get_note=mock_get_note,
    )
    app.splash_view.finish_warmup()

    note_view = app.open_note_view(FIXTURE_NOTE_ID)
    assert resolved_id == FIXTURE_NOTE_ID
    assert note_view is not None
    assert "Creamy garlic pasta" in note_view.clean_body


def test_app_open_note_not_found_displays_error() -> None:
    """Verify 404/not_found error presents snackbar and does not navigate into broken view."""
    def mock_get_note_404(save_id: str) -> None:
        return None

    app = ClayBankApp(
        has_seen_onboarding=True,
        on_get_note=mock_get_note_404,
    )
    app.splash_view.finish_warmup()

    res = app.open_note_view("missing-id-999")
    assert res is None
    assert app.viewport.content is app.app_shell
    assert app.last_snackbar is not None
    assert "Note not found" in app.last_snackbar.message_text


def test_app_open_note_error_dict_displays_error_snackbar() -> None:
    """Verify API error response dictionary triggers error snackbar."""
    def mock_get_note_error(save_id: str) -> dict[str, Any]:
        return {"error": "Conflict: Server updated earlier"}

    app = ClayBankApp(
        has_seen_onboarding=True,
        on_get_note=mock_get_note_error,
    )
    app.splash_view.finish_warmup()

    res = app.open_note_view("conflict-id")
    assert res is None
    assert app.last_snackbar is not None
    assert "Conflict" in app.last_snackbar.message_text


def test_app_note_autosave_updates_coordinator_storage() -> None:
    """Verify note edits flush to coordinator state and trigger on_save_note."""
    saved_payloads: list[dict[str, str]] = []

    def handle_save(save_id: str, markdown: str, updated_at: str) -> dict[str, str]:
        saved_payloads.append({"id": save_id, "markdown": markdown})
        return {"status": "saved"}

    app = ClayBankApp(
        has_seen_onboarding=True,
        saves=[MOCK_SAVE_ITEM],
        notes={FIXTURE_NOTE_ID: SAMPLE_NOTE_MARKDOWN},
        on_save_note=handle_save,
    )
    app.splash_view.finish_warmup()

    app.open_note_view(MOCK_SAVE_ITEM)
    assert app.current_note_view is not None

    # Enter edit mode and simulate user typing
    app.current_note_view.set_editing_mode(True)
    new_md = SAMPLE_NOTE_MARKDOWN.replace("Five ingredients", "Six ingredients")
    app.current_note_view.markdown_editor.text_field.value = new_md
    app.current_note_view.markdown_editor._handle_text_changed(None)

    # Exit edit mode flushes save immediately
    app.current_note_view.set_editing_mode(False)

    assert len(saved_payloads) == 1
    assert "Six ingredients" in saved_payloads[0]["markdown"]
    assert "Six ingredients" in app.notes[FIXTURE_NOTE_ID]


def test_app_note_folder_move_updates_inbox_and_triggers_undo() -> None:
    """Verify folder move in ItemNoteView updates inbox save and exposes 5000ms UndoSnackBar."""
    moved_log: list[tuple[str, str | None]] = []

    def handle_move(save_id: str, folder: str | None) -> None:
        moved_log.append((save_id, folder))

    app = ClayBankApp(
        has_seen_onboarding=True,
        saves=[dict(MOCK_SAVE_ITEM)],
        notes={FIXTURE_NOTE_ID: SAMPLE_NOTE_MARKDOWN},
        on_move_folder=handle_move,
    )
    app.splash_view.finish_warmup()

    app.open_note_view(MOCK_SAVE_ITEM)
    assert app.current_note_view is not None

    # Move to 'Cooking / Baking'
    app.current_note_view._handle_folder_selected("Cooking / Baking")

    assert moved_log == [(FIXTURE_NOTE_ID, "Cooking / Baking")]
    assert app.last_snackbar is not None
    assert app.last_snackbar.duration == 5000
    assert "Moved to Cooking / Baking" in app.last_snackbar.message_text
    # Verify save in inbox was updated
    inbox_save = next(s for s in app.inbox_view._saves if s["id"] == FIXTURE_NOTE_ID)
    assert inbox_save["folder"] == "Cooking / Baking"


def test_app_note_tags_update_updates_inbox_and_triggers_undo() -> None:
    """Verify tags update in ItemNoteView updates inbox save and exposes 5000ms UndoSnackBar."""
    tags_log: list[tuple[str, list[str]]] = []

    def handle_tags(save_id: str, tags: list[str]) -> None:
        tags_log.append((save_id, tags))

    app = ClayBankApp(
        has_seen_onboarding=True,
        saves=[dict(MOCK_SAVE_ITEM)],
        notes={FIXTURE_NOTE_ID: SAMPLE_NOTE_MARKDOWN},
        on_update_tags=handle_tags,
    )
    app.splash_view.finish_warmup()

    app.open_note_view(MOCK_SAVE_ITEM)
    assert app.current_note_view is not None

    app.current_note_view._handle_tags_saved(["italian", "dinner"])

    assert tags_log == [(FIXTURE_NOTE_ID, ["italian", "dinner"])]
    assert app.last_snackbar is not None
    assert app.last_snackbar.duration == 5000
    assert "Tags saved" in app.last_snackbar.message_text

    inbox_save = next(s for s in app.inbox_view._saves if s["id"] == FIXTURE_NOTE_ID)
    assert inbox_save["tags"] == ["italian", "dinner"]


def test_app_note_reprocess_protects_note_body() -> None:
    """Verify reprocess triggers callback and guarantees note body is never modified."""
    reprocessed_ids: list[str] = []

    def handle_reprocess(save_id: str) -> None:
        reprocessed_ids.append(save_id)

    app = ClayBankApp(
        has_seen_onboarding=True,
        saves=[MOCK_SAVE_ITEM],
        notes={FIXTURE_NOTE_ID: SAMPLE_NOTE_MARKDOWN},
        on_reprocess_note=handle_reprocess,
    )
    app.splash_view.finish_warmup()

    app.open_note_view(MOCK_SAVE_ITEM)
    assert app.current_note_view is not None

    app.current_note_view.handle_menu_action("reprocess")

    assert reprocessed_ids == [FIXTURE_NOTE_ID]
    assert app.last_snackbar is not None
    assert "the note body is never touched" in app.last_snackbar.message_text
    assert "Creamy garlic pasta" in app.current_note_view.clean_body


def test_app_note_delete_and_restore_undo_lifecycle() -> None:
    """Verify delete removes save from inbox and undo restores it."""
    deleted_ids: list[str] = []
    restored_ids: list[str] = []

    def handle_delete(save_id: str) -> None:
        deleted_ids.append(save_id)

    def handle_restore(save_id: str) -> None:
        restored_ids.append(save_id)

    app = ClayBankApp(
        has_seen_onboarding=True,
        saves=[dict(MOCK_SAVE_ITEM)],
        notes={FIXTURE_NOTE_ID: SAMPLE_NOTE_MARKDOWN},
        on_delete_note=handle_delete,
        on_restore_note=handle_restore,
    )
    app.splash_view.finish_warmup()

    app.open_note_view(MOCK_SAVE_ITEM)
    assert app.current_note_view is not None

    # Open delete confirm bar
    app.current_note_view.handle_menu_action("delete")
    assert app.current_note_view.delete_container.visible

    # Confirm delete
    app.current_note_view.delete_confirm_bar.confirm_delete()

    assert deleted_ids == [FIXTURE_NOTE_ID]
    assert app.last_snackbar is not None
    assert app.last_snackbar.duration == 5000
    assert "Note deleted" in app.last_snackbar.message_text
    # Save was removed from inbox_view._saves
    assert not any(s["id"] == FIXTURE_NOTE_ID for s in app.inbox_view._saves)

    # Click Undo on the snackbar
    app.last_snackbar.on_undo(None)

    assert restored_ids == [FIXTURE_NOTE_ID]
    # Save is restored in inbox
    assert any(s["id"] == FIXTURE_NOTE_ID for s in app.inbox_view._saves)
    assert app.current_note_view.display_mode_column.visible
