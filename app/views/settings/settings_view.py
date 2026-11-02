"""Complete Settings view for ClayBank (Tab 3).

Assembles the profile card, chat execution engine selector, local model picker,
split storage usage breakdown, system preference switches, conflict recovery surface,
and privacy disclosures.
Derived from Docs/Phases.md Phase 7, Docs/Design.md §8, Docs/UIUX.md §11, and Prototype v2.
"""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    FONT_FAMILY_UI,
    FONT_SIZE_H1,
    SPACING_8,
    SPACING_12,
    SPACING_16,
    SPACING_18,
    SPACING_24,
)
from app.views.settings.chat_model_card import ChatModelCard
from app.views.settings.privacy_banner import PrivacyBanner
from app.views.settings.profile_card import ProfileSyncCard
from app.views.settings.storage_card import StorageUsedCard
from app.views.settings.switch_card import SettingSwitchCard
from app.views.sync.conflict_banner import ConflictRecoveryBanner

SETTINGS_MAX_WIDTH: float = 390.0


class SettingsView(ft.Container):
    """Canonical Tab 3 Settings view for ClayBank."""

    def __init__(
        self,
        *,
        user_name: str | None = None,
        avatar_url: str | None = None,
        last_backup: str | None = None,
        sync_status: str = "Synced",
        chat_model: str = "cloud",
        local_model_id: str = "minicpm5-2b",
        is_local_ready: bool = False,
        is_downloading: bool = False,
        download_progress: float | None = None,
        setup_status_text: str | None = None,
        library_bytes: int | None = 4 * 1024 * 1024,
        local_model_bytes: int | None = int(1.1 * 1024 * 1024 * 1024),
        auto_sort: bool = True,
        weekly_digest: bool = True,
        wifi_only_processing: bool = False,
        quick_save_notification: bool = True,
        conflict_data: dict[str, Any] | None = None,
        on_update_preference: Callable[[str, bool], None] | None = None,
        on_model_change: Callable[[str], None] | None = None,
        on_local_model_pick: Callable[[str], None] | None = None,
        on_request_model_setup: Callable[[str], None] | None = None,
        on_trigger_sync: Callable[[], None] | None = None,
        on_resolve_conflict: Callable[[str, str, str | None], None] | None = None,
        on_overwrite_conflict: Callable[[str, str | None], None] | None = None,
        on_discard_conflict: Callable[[str], None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.theme_mode_val = theme_mode
        self._conflict_data = conflict_data

        self.on_update_preference = on_update_preference
        self.on_model_change = on_model_change
        self.on_local_model_pick = on_local_model_pick
        self.on_request_model_setup = on_request_model_setup
        self.on_trigger_sync = on_trigger_sync
        self.on_resolve_conflict = on_resolve_conflict
        self.on_overwrite_conflict = on_overwrite_conflict
        self.on_discard_conflict = on_discard_conflict

        palette = get_palette(theme_mode)

        # 1. Header Title
        self.title_text = ft.Text(
            value="Settings",
            size=FONT_SIZE_H1,
            weight=ft.FontWeight.W_700,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
        )

        # 2. Conflict Recovery Banner (if active conflict)
        self.conflict_container = ft.Container(visible=False)
        if conflict_data:
            self._mount_conflict_banner(conflict_data)

        # 3. Profile & Sync Card
        self.profile_card = ProfileSyncCard(
            user_name=user_name,
            avatar_url=avatar_url,
            last_backup=last_backup,
            sync_status=sync_status,
            on_sync_click=on_trigger_sync,
            theme_mode=theme_mode,
        )

        # 4. Chat Model Card (Cloud | Local + picker + setup state)
        self.chat_model_card = ChatModelCard(
            chat_model=chat_model,
            local_model_id=local_model_id,
            is_local_ready=is_local_ready,
            is_downloading=is_downloading,
            download_progress=download_progress,
            setup_status_text=setup_status_text,
            on_model_change=on_model_change,
            on_local_model_pick=on_local_model_pick,
            on_request_setup=on_request_model_setup,
            theme_mode=theme_mode,
        )

        # 5. Storage Used Card (Library 4 MB · Local model 1.1 GB)
        self.storage_card = StorageUsedCard(
            library_bytes=library_bytes,
            local_model_bytes=local_model_bytes,
            theme_mode=theme_mode,
        )

        # 6. Preference Switches (Four system toggles)
        self.switch_auto_sort = SettingSwitchCard(
            "Auto-sort new saves",
            field_key="auto_sort",
            value=auto_sort,
            on_change=on_update_preference,
            theme_mode=theme_mode,
        )

        self.switch_weekly_digest = SettingSwitchCard(
            "Weekly digest of unopened saves",
            field_key="weekly_digest",
            value=weekly_digest,
            on_change=on_update_preference,
            theme_mode=theme_mode,
        )

        self.switch_wifi_only = SettingSwitchCard(
            "Wi-Fi only processing",
            field_key="wifi_only_processing",
            value=wifi_only_processing,
            on_change=on_update_preference,
            theme_mode=theme_mode,
        )

        self.switch_quick_save = SettingSwitchCard(
            "Quick-save notification",
            field_key="quick_save_notification",
            value=quick_save_notification,
            on_change=on_update_preference,
            theme_mode=theme_mode,
        )

        # 7. Privacy Disclosure Banner
        self.privacy_banner = PrivacyBanner(
            theme_mode=theme_mode,
        )

        # Assembled Scrollable Content Column
        self.content_column = ft.Column(
            controls=[
                self.title_text,
                self.conflict_container,
                self.profile_card,
                self.chat_model_card,
                self.storage_card,
                self.switch_auto_sort,
                self.switch_weekly_digest,
                self.switch_wifi_only,
                self.switch_quick_save,
                self.privacy_banner,
                ft.Container(height=SPACING_24),  # Bottom padding above nav bar
            ],
            spacing=SPACING_12,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        super().__init__(
            content=self.content_column,
            bgcolor=palette["background"],
            padding=ft.Padding.symmetric(horizontal=SPACING_16, vertical=SPACING_12),
            expand=True,
            alignment=ft.Alignment(0, -1),
        )

    def _mount_conflict_banner(self, conflict_data: dict[str, Any]) -> None:
        """Create and embed the 409 conflict recovery banner."""
        save_id = str(conflict_data.get("save_id", "unknown-save"))
        note_title = conflict_data.get("note_title", "Untitled Note")
        local_markdown = conflict_data.get("local_markdown")
        server_updated_at = conflict_data.get("server_updated_at")

        banner = ConflictRecoveryBanner(
            save_id=save_id,
            note_title=note_title,
            local_markdown=local_markdown,
            server_updated_at=server_updated_at,
            on_keep_both=self.on_resolve_conflict,
            on_overwrite=self.on_overwrite_conflict,
            on_discard=self.on_discard_conflict,
            on_dismiss=self.clear_conflict,
            theme_mode=self.theme_mode_val,
        )
        self.conflict_container.content = banner
        self.conflict_container.visible = True

    def set_conflict(self, conflict_data: dict[str, Any] | None) -> None:
        """Show or hide the conflict recovery banner."""
        self._conflict_data = conflict_data
        if conflict_data:
            self._mount_conflict_banner(conflict_data)
        else:
            self.conflict_container.content = None
            self.conflict_container.visible = False

    def clear_conflict(self) -> None:
        """Dismiss active conflict."""
        self.set_conflict(None)

    def set_sync_status(self, status: str) -> None:
        """Update displayed sync status."""
        self.profile_card.set_sync_status(status)

    def set_last_backup(self, timestamp: str | None) -> None:
        """Update last backup timestamp."""
        self.profile_card.set_last_backup(timestamp)

    def set_chat_model(self, model: str) -> None:
        """Update chat execution engine."""
        self.chat_model_card.set_chat_model(model)

    def set_local_model_id(self, model_id: str) -> None:
        """Update active local model ID."""
        self.chat_model_card.set_local_model_id(model_id)

    def set_download_state(
        self,
        *,
        is_downloading: bool,
        progress: float | None = None,
        status_text: str | None = None,
        is_ready: bool = False,
    ) -> None:
        """Update local model setup progress."""
        self.chat_model_card.set_download_state(
            is_downloading=is_downloading,
            progress=progress,
            status_text=status_text,
            is_ready=is_ready,
        )

    def set_preference(self, key: str, val: bool) -> None:
        """Update one of the four switch values."""
        if key == "auto_sort":
            self.switch_auto_sort.set_value(val)
        elif key == "weekly_digest":
            self.switch_weekly_digest.set_value(val)
        elif key == "wifi_only_processing":
            self.switch_wifi_only.set_value(val)
        elif key == "quick_save_notification":
            self.switch_quick_save.set_value(val)
