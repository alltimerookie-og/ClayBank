"""Test suite for Phase 8 Application Shell & Lifecycle Integration.

Validates the first-save permission gate, settings toggle reactivity, external capture intent
handling (paste_and_save, share_target, open_app), shell recovery, and strict 4-tab invariant.
Derived from Docs/Phases.md Phase 8, Docs/Architecture.md §3.3, and Docs/Memory.md §5.
"""

from __future__ import annotations

from typing import Any
import pytest

from app.app import ClayBankApp
from app.shell.nav import TAB_FOLDERS, TAB_INBOX, TAB_SEARCH, TAB_SETTINGS
from app.views.capture import (
    ACTION_OPEN_APP,
    ACTION_PASTE_AND_SAVE,
    ACTION_SHARE_TARGET,
    NOTIFICATION_ID_QUICK_SAVE,
    NotificationCoordinator,
)


class TestPhase8Integration:
    """Integration test suite for Phase 8 capture surfaces and notification coordinator."""

    def test_app_initialization_does_not_request_permission(self) -> None:
        """Verify no notification permission is requested during app startup or settings view creation."""
        perm_requested = False

        def mock_perm() -> bool:
            nonlocal perm_requested
            perm_requested = True
            return True

        app = ClayBankApp(
            has_seen_onboarding=True,
            on_request_notification_permission=mock_perm,
        )

        assert not perm_requested
        assert app.notification_coordinator.permission_state == "not_requested"
        assert not app.notification_coordinator.is_notification_active

    def test_first_save_triggers_permission_gate(self) -> None:
        """Verify the first successful save prompts for permission and posts notification when granted."""
        perm_calls: list[bool] = []
        posted_notifications: list[dict[str, Any]] = []

        def mock_perm() -> bool:
            perm_calls.append(True)
            return True

        def mock_post(payload: dict[str, Any]) -> bool:
            posted_notifications.append(payload)
            return True

        app = ClayBankApp(
            has_seen_onboarding=True,
            on_request_notification_permission=mock_perm,
            on_post_notification=mock_post,
        )

        # Complete first save
        app.handle_capture_success({"url": "https://first-save.example.com", "id": "save-1"})

        assert len(perm_calls) == 1
        assert app.notification_coordinator.has_prompted_for_permission
        assert app.notification_coordinator.has_completed_first_save
        assert app.notification_coordinator.permission_state == "granted"
        assert app.notification_coordinator.is_notification_active
        assert len(posted_notifications) == 1
        assert posted_notifications[0]["id"] == NOTIFICATION_ID_QUICK_SAVE

        # Complete second save - must NOT re-prompt permission
        app.handle_capture_success({"url": "https://second-save.example.com", "id": "save-2"})
        assert len(perm_calls) == 1

    def test_first_save_with_preference_disabled_skips_permission(self) -> None:
        """Verify permission is not requested if quick_save_notification is disabled in settings."""
        perm_calls: list[bool] = []

        app = ClayBankApp(
            has_seen_onboarding=True,
            settings={"quick_save_notification": False},
            on_request_notification_permission=lambda: perm_calls.append(True) or True,
        )

        app.handle_capture_success({"url": "https://save.example.com", "id": "save-1"})

        assert len(perm_calls) == 0
        assert not app.notification_coordinator.has_prompted_for_permission
        assert app.notification_coordinator.has_completed_first_save
        assert not app.notification_coordinator.is_notification_active

    def test_settings_toggle_reactively_controls_notification(self) -> None:
        """Verify toggling quick_save_notification switch dismisses and restores notification."""
        cancelled_notifications: list[int] = []
        posted_notifications: list[int] = []

        app = ClayBankApp(
            has_seen_onboarding=True,
            on_request_notification_permission=lambda: True,
            on_post_notification=lambda payload: bool(posted_notifications.append(payload["id"]) or True),
            on_dismiss_notification=lambda nid: bool(cancelled_notifications.append(nid) or True),
        )

        # Trigger initial save to grant and post
        app.handle_capture_success({"url": "https://example.com", "id": "save-1"})
        assert app.notification_coordinator.is_notification_active
        assert posted_notifications == [NOTIFICATION_ID_QUICK_SAVE]

        # Toggle OFF in settings
        app.handle_preference_change("quick_save_notification", False)
        assert not app.notification_coordinator.is_notification_active
        assert cancelled_notifications == [NOTIFICATION_ID_QUICK_SAVE]

        # Toggle ON in settings - restores without re-prompt
        app.handle_preference_change("quick_save_notification", True)
        assert app.notification_coordinator.is_notification_active
        assert len(posted_notifications) == 2

    def test_external_capture_paste_and_save_opens_paste_sheet(self) -> None:
        """Verify handle_external_capture(ACTION_PASTE_AND_SAVE) opens paste sheet with notification attribution."""
        app = ClayBankApp(has_seen_onboarding=True)
        assert not app.is_paste_sheet_open

        app.handle_external_capture(ACTION_PASTE_AND_SAVE)

        assert app.is_paste_sheet_open
        assert app.paste_sheet is not None
        assert app.paste_sheet.source_app == "notification"

    def test_external_capture_share_target_prefills_intent_url(self) -> None:
        """Verify handle_external_capture(ACTION_SHARE_TARGET) prefills shared URL."""
        app = ClayBankApp(has_seen_onboarding=True)
        assert not app.is_paste_sheet_open

        app.handle_external_capture(ACTION_SHARE_TARGET, url="https://twitter.com/post/98765")

        assert app.is_paste_sheet_open
        assert app.paste_sheet is not None
        assert app.paste_sheet.url_field.value == "https://twitter.com/post/98765"
        assert app.paste_sheet.source_app == "share_target"

    def test_external_capture_open_app_switches_to_inbox(self) -> None:
        """Verify handle_external_capture(ACTION_OPEN_APP) switches active tab to Inbox."""
        app = ClayBankApp(has_seen_onboarding=True)
        app.transition_to_shell()

        # Switch to Folders first
        app.app_shell.set_tab(TAB_FOLDERS)
        assert app.app_shell.selected_index == TAB_FOLDERS

        # Trigger Open App action
        app.handle_external_capture(ACTION_OPEN_APP)
        assert app.app_shell.selected_index == TAB_INBOX

    def test_external_capture_recovers_app_shell_if_subview_active(self) -> None:
        """Verify external capture recovers app shell if note view or modal subview was displayed."""
        app = ClayBankApp(has_seen_onboarding=True)
        app.transition_to_shell()

        # Open Note view
        save_item = {"id": "test-save-1", "title": "Test Item", "url": "https://example.com"}
        app.open_note_view(save_item)
        assert app.viewport.content != app.app_shell
        assert app.current_note_view is not None

        # Trigger share target action
        app.handle_external_capture(ACTION_SHARE_TARGET, url="https://new-item.com")

        assert app.viewport.content == app.app_shell
        assert app.current_note_view is None
        assert app.is_paste_sheet_open
        assert app.paste_sheet is not None
        assert app.paste_sheet.url_field.value == "https://new-item.com"

    def test_strict_four_tab_invariant_maintained(self) -> None:
        """Verify the 4-tab shell structure remains unchanged."""
        app = ClayBankApp(has_seen_onboarding=True)
        app.transition_to_shell()

        nav_destinations = app.app_shell.nav_bar.destinations
        assert len(nav_destinations) == 4
        assert len(app.app_shell.tab_views) == 4
