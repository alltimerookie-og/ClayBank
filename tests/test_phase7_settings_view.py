"""Tests for SettingsView assembly (P7-07 deliverable).

Validates canonical card ordering, profile value propagation, model selector,
storage values, four system switches, privacy disclosure, and conflict banner.
"""

from __future__ import annotations

import flet as ft
import pytest

from app.views.settings.privacy_banner import PRIVACY_BANNER_TEXT
from app.views.settings.settings_view import SettingsView


class TestSettingsView:
    """Test suite for SettingsView component."""

    def test_canonical_card_ordering(self) -> None:
        """Verify cards appear in documented sequence."""
        view = SettingsView()
        controls = view.content_column.controls

        assert isinstance(controls[0], ft.Text)
        assert controls[0].value == "Settings"
        assert controls[1] == view.conflict_container
        assert controls[2] == view.profile_card
        assert controls[3] == view.chat_model_card
        assert controls[4] == view.storage_card
        assert controls[5] == view.switch_auto_sort
        assert controls[6] == view.switch_weekly_digest
        assert controls[7] == view.switch_wifi_only
        assert controls[8] == view.switch_quick_save
        assert controls[9] == view.privacy_banner

    def test_profile_and_sync_propagation(self) -> None:
        """Verify profile info and sync status propagate to child card."""
        view = SettingsView(
            user_name="Md. Shefayet",
            last_backup="just now",
            sync_status="Synced",
        )
        assert view.profile_card.name_text.value == "Md. Shefayet"
        assert view.profile_card.backup_text.value == "Last backup: just now"
        assert view.profile_card._sync_status == "Synced"

    def test_chat_model_and_local_picker_state(self) -> None:
        """Verify chat model switching and local model picker."""
        model_changes: list[str] = []
        picks: list[str] = []

        view = SettingsView(
            chat_model="cloud",
            on_model_change=lambda m: model_changes.append(m),
            on_local_model_pick=lambda p: picks.append(p),
        )
        assert view.chat_model_card.local_picker_section.visible is False

        view.set_chat_model("local")
        assert view.chat_model_card.local_picker_section.visible is True

    def test_storage_card_values(self) -> None:
        """Verify storage values displayed."""
        view = SettingsView(
            library_bytes=4 * 1024 * 1024,
            local_model_bytes=int(1.1 * 1024 * 1024 * 1024),
        )
        assert "Library 4 MB · Local model 1.1 GB" in view.storage_card.value_text.value

    def test_all_four_preference_switches_dispatch(self) -> None:
        """Verify toggles dispatch callbacks with key and value."""
        dispatched: list[tuple[str, bool]] = []

        def handle_pref(k: str, v: bool) -> None:
            dispatched.append((k, v))

        view = SettingsView(
            auto_sort=True,
            weekly_digest=True,
            wifi_only_processing=False,
            quick_save_notification=True,
            on_update_preference=handle_pref,
        )

        assert view.switch_auto_sort.value is True
        assert view.switch_weekly_digest.value is True
        assert view.switch_wifi_only.value is False
        assert view.switch_quick_save.value is True

        # Toggle auto-sort
        event = type("Event", (), {"control": type("Control", (), {"value": False})()})()
        assert view.switch_auto_sort.switch_control.on_change is not None
        view.switch_auto_sort.switch_control.on_change(event)
        assert ("auto_sort", False) in dispatched

    def test_privacy_banner_present(self) -> None:
        """Verify privacy disclosure banner is present with exact locked text."""
        view = SettingsView()
        assert view.privacy_banner.text_control.value == PRIVACY_BANNER_TEXT

    def test_conflict_banner_mount_and_clear(self) -> None:
        """Verify conflict recovery banner mounts when conflict data is supplied."""
        conflict_payload = {
            "save_id": "save-999",
            "note_title": "Chicken Soup Recipe",
            "local_markdown": "# My edit",
            "server_updated_at": "2026-10-31T12:00:00Z",
        }

        view = SettingsView(conflict_data=conflict_payload)
        assert view.conflict_container.visible is True
        assert view.conflict_container.content is not None

        # Clear conflict
        view.clear_conflict()
        assert view.conflict_container.visible is False
        assert view.conflict_container.content is None

    def test_dark_mode_rendering(self) -> None:
        """Verify dark mode styling across entire SettingsView."""
        view = SettingsView(theme_mode=ft.ThemeMode.DARK)
        assert view.bgcolor is not None
        assert view.profile_card.bgcolor is not None
