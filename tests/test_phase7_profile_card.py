"""Tests for ProfileSyncCard (P7-01 deliverable).

Validates avatar initials, user name formatting, backup timestamp labels,
sync status states (Synced, Syncing, Offline, Conflict), theme compatibility,
and interaction callbacks.
"""

from __future__ import annotations

import flet as ft
import pytest

from app.shell.tokens import MIN_TOUCH_TARGET
from app.views.settings.profile_card import ProfileSyncCard, _extract_initials, _format_backup_label


class TestProfileSyncCard:
    """Test suite for ProfileSyncCard component."""

    def test_initials_extraction(self) -> None:
        """Verify initials extraction logic."""
        assert _extract_initials("Md. Shefayet") == "MS"
        assert _extract_initials("Shefayet") == "SH"
        assert _extract_initials("Jane Alice Doe") == "JD"
        assert _extract_initials("") == "LU"
        assert _extract_initials(None) == "LU"

    def test_backup_label_formatting(self) -> None:
        """Verify formatting of backup timestamps."""
        assert _format_backup_label("just now") == "Last backup: just now"
        assert _format_backup_label("Last backup: 5 mins ago") == "Last backup: 5 mins ago"
        assert _format_backup_label(None) == "No backups yet"
        assert _format_backup_label("") == "No backups yet"

        # Valid ISO timestamp
        iso_res = _format_backup_label("2026-10-31T12:00:00Z")
        assert "Last backup: 2026-10-31 12:00 UTC" in iso_res

    def test_default_rendering(self) -> None:
        """Verify default construction with fallback name and synced status."""
        card = ProfileSyncCard()
        assert card.name_text.value == "Local User"
        assert card.backup_text.value == "No backups yet"
        assert card.avatar is not None
        assert isinstance(card.avatar.content, ft.Text)
        assert card.avatar.content.value == "LU"
        assert card.status_chip.height == MIN_TOUCH_TARGET

    def test_custom_profile_info(self) -> None:
        """Verify profile info populated with prototype values."""
        card = ProfileSyncCard(
            user_name="Md. Shefayet",
            last_backup="just now",
            sync_status="Synced",
        )
        assert card.name_text.value == "Md. Shefayet"
        assert card.backup_text.value == "Last backup: just now"
        assert isinstance(card.avatar.content, ft.Text)
        assert card.avatar.content.value == "MS"

    def test_sync_status_states(self) -> None:
        """Verify styling and controls for Synced, Syncing, Offline, and Conflict."""
        # Synced
        synced_card = ProfileSyncCard(sync_status="Synced")
        chip_row = synced_card.status_chip.content
        assert isinstance(chip_row, ft.Row)
        assert any(isinstance(c, ft.Icon) for c in chip_row.controls)

        # Syncing
        syncing_card = ProfileSyncCard(sync_status="Syncing…")
        syncing_row = syncing_card.status_chip.content
        assert isinstance(syncing_row, ft.Row)
        # Should contain ProgressRing instead of static check icon
        assert any(isinstance(c, ft.ProgressRing) for c in syncing_row.controls)

        # Offline
        offline_card = ProfileSyncCard(sync_status="Offline")
        assert offline_card.status_chip is not None

        # Conflict
        conflict_card = ProfileSyncCard(sync_status="Conflict")
        assert conflict_card.status_chip is not None

    def test_sync_callback_and_click_protection(self) -> None:
        """Verify sync callback triggers on click and prevents duplicate triggers when syncing."""
        calls: list[int] = []

        def on_sync() -> None:
            calls.append(1)

        card = ProfileSyncCard(sync_status="Synced", on_sync_click=on_sync)
        assert card.status_chip.on_click is not None
        card.status_chip.on_click(None)
        assert len(calls) == 1

        # Now test when status is Syncing...
        syncing_card = ProfileSyncCard(sync_status="Syncing…", on_sync_click=on_sync)
        # on_click should be disabled on the container when syncing
        assert syncing_card.status_chip.on_click is None
        assert len(calls) == 1  # No additional calls

    def test_dynamic_setters(self) -> None:
        """Verify dynamic state updates."""
        card = ProfileSyncCard(user_name="Initial User", sync_status="Synced")
        assert card.name_text.value == "Initial User"

        card.set_user_name("Updated Shefayet")
        assert card.name_text.value == "Updated Shefayet"
        assert isinstance(card.avatar.content, ft.Text)
        assert card.avatar.content.value == "US"

        card.set_last_backup("just now")
        assert card.backup_text.value == "Last backup: just now"

        card.set_sync_status("Offline")
        assert card._sync_status == "Offline"

    def test_dark_mode_support(self) -> None:
        """Verify rendering under dark theme."""
        card_dark = ProfileSyncCard(theme_mode=ft.ThemeMode.DARK)
        assert card_dark.bgcolor is not None
        assert card_dark.avatar.bgcolor is not None
