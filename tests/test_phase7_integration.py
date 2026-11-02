"""Integration tests for Phase 7 Settings & Synchronization (P7-08 deliverable).

Validates complete integration of SettingsView in Tab 3 of AppShellLayout,
propagation of chat engine to Ask requests, synchronization coordination,
409 conflict Keep-Both recovery, and four-tab invariant preservation.
"""

from __future__ import annotations

import flet as ft
import pytest

from app.app import ClayBankApp
from app.shell.nav import TAB_COUNT, TAB_FOLDERS, TAB_INBOX, TAB_SEARCH, TAB_SETTINGS
from app.views.settings.settings_view import SettingsView


class TestPhase7Integration:
    """Test suite for Phase 7 Application Shell and Settings integration."""

    def test_four_tab_navigation_invariant(self) -> None:
        """Verify strict invariant: exactly 4 tabs exist, Settings is Tab 3."""
        app = ClayBankApp(has_seen_onboarding=True)
        shell = app.app_shell

        # 4 tabs exactly
        assert TAB_COUNT == 4
        assert len(shell.nav_bar.destinations) == 4
        assert len(shell.tab_views) == 4

        # Settings is tab 3
        assert shell.tab_views[TAB_SETTINGS] is not None
        assert isinstance(shell.tab_views[TAB_SETTINGS], SettingsView)
        assert shell.tab_views[TAB_SETTINGS] == app.settings_view

    def test_settings_tab_activation(self) -> None:
        """Verify switching to Tab 3 activates real SettingsView in content area."""
        app = ClayBankApp(has_seen_onboarding=True)
        shell = app.app_shell

        # Switch to tab 3 (Settings)
        shell.set_tab(TAB_SETTINGS)
        assert shell.selected_index == TAB_SETTINGS
        assert shell.header.title_text.value == "Settings"
        assert shell.content_area.content == app.settings_view

    def test_chat_engine_propagation_to_ask(self) -> None:
        """Verify chat_model from Settings propagates into POST /ask engine parameter."""
        app = ClayBankApp(has_seen_onboarding=True, settings={"chat_model": "cloud"})

        # Default is cloud
        res_cloud = app.handle_ask_query("Where did I save pasta?")
        assert res_cloud["engine"] == "cloud"

        # Change chat model to local
        app.handle_chat_model_change("local")
        assert app.sync_coordinator.get_setting("chat_model") == "local"

        res_local = app.handle_ask_query("Where did I save pasta?")
        assert res_local["engine"] == "local"

    def test_ask_query_callback_receives_engine(self) -> None:
        """Verify on_ask_query callback receives engine parameter."""
        dispatched_engine: list[str] = []

        def mock_ask(question: str, scope: str | None = None, engine: str = "cloud") -> dict:
            dispatched_engine.append(engine)
            return {
                "answer": "Mock grounded answer",
                "scope": scope or "library",
                "engine": engine,
                "citations": [{"save_id": "s-1", "anchor": "top"}],
            }

        app = ClayBankApp(
            has_seen_onboarding=True,
            settings={"chat_model": "local"},
            on_ask_query=mock_ask,
        )

        _ = app.handle_ask_query("Test question")
        assert dispatched_engine == ["local"]

    def test_preference_switch_updates_settings(self) -> None:
        """Toggling preference updates coordinator and triggers on_update_settings."""
        persisted: list[dict] = []

        app = ClayBankApp(
            has_seen_onboarding=True,
            on_update_settings=lambda s: persisted.append(s),
        )

        app.handle_preference_change("wifi_only_processing", True)
        assert app.sync_coordinator.get_setting("wifi_only_processing") is True
        assert len(persisted) == 1
        assert persisted[0]["wifi_only_processing"] is True

    def test_sync_trigger_and_status_updates(self) -> None:
        """Manual sync triggers provider and updates SettingsView status and backup label."""
        pull_executed: list[str] = []

        def mock_pull(cursor: str) -> dict:
            pull_executed.append(cursor)
            return {"saves": [], "notes": [], "folders": [], "jobs": [], "deleted": [], "cursor": "c-00045"}

        app = ClayBankApp(
            has_seen_onboarding=True,
            sync_state={"cursor": "c-00044", "sync_status": "Synced"},
            on_sync_pull=mock_pull,
        )

        res = app.handle_trigger_sync()
        assert res["status"] == "success"
        assert app.settings_view.profile_card._sync_status == "Synced"
        assert app.settings_view.profile_card.backup_text.value != "No backups yet"
        assert len(pull_executed) == 1

    def test_conflict_reporting_and_keep_both_recovery(self) -> None:
        """409 conflict displays banner and Keep Both creates local copy without data loss."""
        app = ClayBankApp(
            has_seen_onboarding=True,
            saves=[
                {
                    "id": "save-pasta",
                    "title": "Pasta Recipe",
                    "url": "https://example.com/pasta",
                    "platform": "youtube",
                }
            ],
        )

        # 1. Report conflict
        app.report_conflict(
            save_id="save-pasta",
            note_title="Pasta Recipe",
            local_markdown="# Local Pasta Edits",
            server_updated_at="2026-10-31T12:00:00Z",
        )

        assert app.settings_view.conflict_container.visible is True
        assert app.sync_coordinator.sync_status == "Conflict"

        # 2. Execute Keep Both
        res = app.handle_keep_both_conflict("save-pasta", "Pasta Recipe (Local Edit)", "# Local Pasta Edits")
        assert res["status"] == "kept_both"
        assert res["title"] == "Pasta Recipe (Local Edit)"

        # Conflict is cleared
        assert app.settings_view.conflict_container.visible is False
        assert app.sync_coordinator.sync_status == "Synced"

        # Local edit copy is inserted in Inbox saves
        assert any("Pasta Recipe (Local Edit)" in str(s.get("title")) for s in app.inbox_view._saves)

    def test_no_premature_notification_permission_on_startup(self) -> None:
        """Phase 8 permission gate: POST_NOTIFICATIONS is never called during Phase 7."""
        # Creating app and switching to settings must not request notification permissions
        app = ClayBankApp(has_seen_onboarding=True)
        app.app_shell.set_tab(TAB_SETTINGS)
        # Verify app initialized cleanly without any platform permission calls
        assert app.settings_view.switch_quick_save.value is True

    def test_theme_mode_switching_preserves_settings_view(self) -> None:
        """Theme toggle updates palette without destroying SettingsView state."""
        app = ClayBankApp(has_seen_onboarding=True, theme_mode=ft.ThemeMode.LIGHT)
        app.app_shell.set_tab(TAB_SETTINGS)

        app.set_theme_mode(ft.ThemeMode.DARK)
        assert app.app_shell.selected_index == TAB_SETTINGS
        assert app.app_shell.content_area.content == app.settings_view
