"""Unit tests for P4-09: Conflict Banner and Delete Confirmation."""

from __future__ import annotations

import flet as ft

from app.views.note.note_alerts import ConflictBanner, DeleteConfirmBar


def test_conflict_banner_initial_state_and_actions() -> None:
    """Verify conflict banner renders explanation and emits recovery actions."""
    kept = False
    discarded = False

    def on_keep() -> None:
        nonlocal kept
        kept = True

    def on_discard() -> None:
        nonlocal discarded
        discarded = True

    banner = ConflictBanner(
        on_keep_local=on_keep,
        on_discard_local=on_discard,
    )

    assert "Conflict" in banner.message_text.value
    banner.keep_local()
    assert kept

    banner.discard_local()
    assert discarded


def test_delete_confirm_bar_initial_state() -> None:
    """Verify initial prompt and buttons for delete confirmation."""
    bar = DeleteConfirmBar()

    assert bar.prompt_text.value == "Delete this note and its save?"
    assert not bar.is_deleted
    assert bar.buttons_row.visible


def test_delete_confirm_bar_confirm_and_reset() -> None:
    """Verify confirming delete updates prompt, hides buttons, and invokes callback."""
    deleted = False

    def on_delete() -> None:
        nonlocal deleted
        deleted = True

    bar = DeleteConfirmBar(on_confirm_delete=on_delete)

    bar.confirm_delete()
    assert deleted
    assert bar.is_deleted
    assert bar.prompt_text.value == "This note is deleted."
    assert not bar.buttons_row.visible

    # Reset state (e.g., when user hits Undo)
    bar.reset_state()
    assert not bar.is_deleted
    assert bar.prompt_text.value == "Delete this note and its save?"
    assert bar.buttons_row.visible


def test_delete_confirm_bar_cancel() -> None:
    """Verify cancel action invokes on_cancel callback."""
    cancelled = False

    def on_cancel() -> None:
        nonlocal cancelled
        cancelled = True

    bar = DeleteConfirmBar(on_cancel=on_cancel)
    bar.cancel()
    assert cancelled


def test_note_alerts_dark_mode() -> None:
    """Verify dark mode initialization for both components."""
    banner = ConflictBanner(theme_mode=ft.ThemeMode.DARK)
    bar = DeleteConfirmBar(theme_mode=ft.ThemeMode.DARK)

    assert banner.theme_mode_val == ft.ThemeMode.DARK
    assert bar.theme_mode_val == ft.ThemeMode.DARK
