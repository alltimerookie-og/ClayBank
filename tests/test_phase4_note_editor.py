"""Unit tests for P4-06: Markdown Note Editor with Auto-Save UX."""

from __future__ import annotations

import time
import flet as ft

from app.views.note.note_editor import MarkdownNoteEditor


def test_note_editor_initial_state() -> None:
    """Verify editor initializes with monospace font, initial text, and clean status."""
    editor = MarkdownNoteEditor(
        save_id="save-001",
        initial_markdown="# Initial content",
    )

    assert editor.text_field.value == "# Initial content"
    assert editor.text_field.text_style is not None
    assert editor.text_field.text_style.font_family == "ui-monospace, monospace"
    assert editor.save_status == "Saved on device ✓"
    assert not editor.is_dirty


def test_note_editor_typing_triggers_saving_status() -> None:
    """Verify typing updates status to 'Saving…' and marks state as dirty."""
    editor = MarkdownNoteEditor(
        save_id="save-001",
        initial_markdown="# Hello",
        debounce_interval=0.1,  # Short debounce for test
    )

    editor.text_field.value = "# Hello World"
    editor._handle_text_changed(None)

    assert editor.is_dirty
    assert editor.save_status == "Saving…"


def test_note_editor_debounced_auto_save_success() -> None:
    """Verify debounced timer triggers save callback and marks clean."""
    saved_payloads: list[tuple[str, str, str]] = []

    def on_save(save_id: str, content: str, updated_at: str) -> None:
        saved_payloads.append((save_id, content, updated_at))

    editor = MarkdownNoteEditor(
        save_id="save-001",
        initial_markdown="# Old",
        on_save_note=on_save,
        debounce_interval=0.05,
    )

    editor.text_field.value = "# New Content"
    editor._handle_text_changed(None)

    # Wait for debounce timer to fire
    time.sleep(0.12)

    assert len(saved_payloads) == 1
    assert saved_payloads[0][0] == "save-001"
    assert saved_payloads[0][1] == "# New Content"
    assert not editor.is_dirty
    assert editor.save_status == "Saved on device ✓"


def test_note_editor_offline_status_feedback() -> None:
    """Verify offline response displays 'Saved on device ✓ (offline)'."""
    def on_save(save_id: str, content: str, updated_at: str) -> dict[str, bool]:
        return {"offline": True}

    editor = MarkdownNoteEditor(
        save_id="save-002",
        initial_markdown="Draft",
        on_save_note=on_save,
        debounce_interval=0.05,
    )

    editor.text_field.value = "Draft updated"
    editor._handle_text_changed(None)

    time.sleep(0.12)
    assert editor.save_status == "Saved on device ✓ (offline)"


def test_note_editor_failure_preserves_content() -> None:
    """Verify error during save displays error status and preserves unsaved text."""
    def on_save_fail(save_id: str, content: str, updated_at: str) -> None:
        raise RuntimeError("Network timeout")

    editor = MarkdownNoteEditor(
        save_id="save-003",
        initial_markdown="Draft",
        on_save_note=on_save_fail,
        debounce_interval=0.05,
    )

    editor.text_field.value = "Draft with error"
    editor._handle_text_changed(None)

    time.sleep(0.12)
    assert "Save failed" in editor.save_status
    assert editor.text_field.value == "Draft with error"


def test_note_editor_toolbar_action_applies_syntax() -> None:
    """Verify toolbar action applies syntax and sets dirty state."""
    editor = MarkdownNoteEditor(
        save_id="save-004",
        initial_markdown="Item",
        debounce_interval=0.05,
    )

    editor.cursor_start = 0
    editor.cursor_end = 4
    editor.handle_toolbar_action("b")

    assert editor.text_field.value == "**Item**"
    assert editor.is_dirty
    assert editor.save_status == "Saving…"


def test_note_editor_flush_pending_save_on_exit() -> None:
    """Verify flush_pending_save immediately executes persistence and cancels timer."""
    saved_payloads: list[str] = []

    def on_save(save_id: str, content: str, updated_at: str) -> None:
        saved_payloads.append(content)

    editor = MarkdownNoteEditor(
        save_id="save-005",
        initial_markdown="Start",
        on_save_note=on_save,
        debounce_interval=10.0,  # Long timer that won't fire during test
    )

    editor.text_field.value = "Exiting with changes"
    editor._handle_text_changed(None)
    assert editor.is_dirty

    # Immediately flush
    editor.flush_pending_save()

    assert not editor.is_dirty
    assert len(saved_payloads) == 1
    assert saved_payloads[0] == "Exiting with changes"
    assert editor.save_status == "Saved on device ✓"
