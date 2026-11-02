"""Tests for ConflictRecoveryBanner (P7-05 deliverable).

Validates 409 conflict message display, Keep Both title generation,
destructive Overwrite confirmation gate, Discard Local action, loading states,
error resilience, and theme modes.
"""

from __future__ import annotations

import flet as ft
import pytest

from app.shell.tokens import MIN_TOUCH_TARGET
from app.views.sync.conflict_banner import (
    CONFLICT_MESSAGE,
    ConflictRecoveryBanner,
    create_local_edit_title,
)


class TestConflictRecoveryBanner:
    """Test suite for ConflictRecoveryBanner component."""

    def test_local_edit_title_formatting(self) -> None:
        """Verify canonical '<Title> (Local Edit)' naming pattern."""
        assert create_local_edit_title("Weeknight Curry") == "Weeknight Curry (Local Edit)"
        assert create_local_edit_title(None) == "Untitled Note (Local Edit)"
        assert create_local_edit_title("") == "Untitled Note (Local Edit)"
        assert create_local_edit_title("Weeknight Curry (Local Edit)") == "Weeknight Curry (Local Edit)"

    def test_banner_content(self) -> None:
        """Verify conflict message and context header."""
        banner = ConflictRecoveryBanner(
            save_id="018f4c1a-0000-7de6-9c8e-000000000001",
            note_title="Pasta Carbonara",
            server_updated_at="2026-10-31T12:00:00Z",
        )
        assert banner.title_text.value == CONFLICT_MESSAGE
        assert "Pasta Carbonara" in banner.info_text.value
        assert "2026-10-31T12:00:00Z" in banner.info_text.value
        assert banner.keep_both_btn.height == MIN_TOUCH_TARGET
        assert banner.overwrite_btn.height == MIN_TOUCH_TARGET
        assert banner.discard_btn.height == MIN_TOUCH_TARGET

    def test_keep_both_action(self) -> None:
        """Keep Both passes original save_id, formatted title, and local markdown."""
        dispatched: list[tuple[str, str, str | None]] = []
        dismissed: list[bool] = []

        def handle_keep_both(sid: str, title: str, md: str | None) -> None:
            dispatched.append((sid, title, md))

        banner = ConflictRecoveryBanner(
            save_id="save-123",
            note_title="Original Recipe",
            local_markdown="# My local edit",
            on_keep_both=handle_keep_both,
            on_dismiss=lambda: dismissed.append(True),
        )

        assert banner.keep_both_btn.on_click is not None
        banner.keep_both_btn.on_click(None)

        assert dispatched == [("save-123", "Original Recipe (Local Edit)", "# My local edit")]
        assert dismissed == [True]

    def test_overwrite_requires_explicit_confirmation(self) -> None:
        """Clicking Overwrite Server reveals confirmation prompt without executing immediately."""
        overwritten: list[tuple[str, str | None]] = []

        def handle_overwrite(sid: str, md: str | None) -> None:
            overwritten.append((sid, md))

        banner = ConflictRecoveryBanner(
            save_id="save-123",
            note_title="Original Recipe",
            local_markdown="# Forcing this",
            on_overwrite=handle_overwrite,
        )

        # 1. Click initial Overwrite button
        assert banner.actions_row.visible is True
        assert banner.confirm_row.visible is False
        assert banner.overwrite_btn.on_click is not None
        banner.overwrite_btn.on_click(None)

        # Confirmation prompt shown, nothing dispatched yet
        assert banner.actions_row.visible is False
        assert banner.confirm_row.visible is True
        assert len(overwritten) == 0

        # 2. Click Cancel
        assert banner.confirm_cancel_btn.on_click is not None
        banner.confirm_cancel_btn.on_click(None)
        assert banner.actions_row.visible is True
        assert banner.confirm_row.visible is False
        assert len(overwritten) == 0

        # 3. Click Overwrite again and Confirm
        banner.overwrite_btn.on_click(None)
        assert banner.confirm_yes_btn.on_click is not None
        banner.confirm_yes_btn.on_click(None)

        # Dispatched
        assert overwritten == [("save-123", "# Forcing this")]

    def test_discard_action(self) -> None:
        """Discard local reverts by calling on_discard with save_id."""
        discarded: list[str] = []
        dismissed: list[bool] = []

        banner = ConflictRecoveryBanner(
            save_id="save-456",
            on_discard=lambda sid: discarded.append(sid),
            on_dismiss=lambda: dismissed.append(True),
        )

        assert banner.discard_btn.on_click is not None
        banner.discard_btn.on_click(None)

        assert discarded == ["save-456"]
        assert dismissed == [True]

    def test_error_handling_preserves_banner(self) -> None:
        """If a recovery callback raises an error, banner displays error and remains active."""
        def failing_keep_both(sid: str, title: str, md: str | None) -> None:
            raise RuntimeError("Database write failed")

        banner = ConflictRecoveryBanner(
            save_id="save-fail",
            on_keep_both=failing_keep_both,
        )

        assert banner.keep_both_btn.on_click is not None
        banner.keep_both_btn.on_click(None)

        assert banner.error_text.visible is True
        assert "Database write failed" in banner.error_text.value
        assert banner._is_resolving is False

    def test_dark_mode_rendering(self) -> None:
        """Verify dark mode styling."""
        banner = ConflictRecoveryBanner(
            save_id="save-dark",
            theme_mode=ft.ThemeMode.DARK,
        )
        assert banner.bgcolor is not None
