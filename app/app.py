"""Top-level ClayBank Application Coordinator.

Orchestrates navigation lifecycle across Splash -> Onboarding -> AppShell,
binds the AddLinkPasteSheet modal, coordinates Inbox data refreshes, and triggers
UndoSnackBar feedback for review actions.

Derived from Docs/Phases.md Phase 2, Docs/UIUX.md, and Prototype v2.
"""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from app.shell.app_shell import AppShellLayout
from app.shell.nav import TAB_INBOX
from app.shell.theme import get_palette
from app.ui.snackbar import UndoSnackBar
from app.views.inbox_view import InboxView
from app.views.onboarding_view import OnboardingView
from app.views.paste_sheet import AddLinkPasteSheet
from app.views.splash_view import SplashView

UNDO_DURATION_MS: int = 5000


class ClayBankApp(ft.Container):
    """Top-level ClayBank application manager."""

    def __init__(
        self,
        *,
        has_seen_onboarding: bool = False,
        saves: list[dict[str, Any]] | None = None,
        suggestions: list[dict[str, Any]] | None = None,
        active_jobs: list[dict[str, Any]] | None = None,
        on_save_capture: Callable[[dict[str, Any]], Any] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.has_seen_onboarding = has_seen_onboarding
        self.theme_mode_val = theme_mode
        self.on_save_capture = on_save_capture

        self.last_snackbar: UndoSnackBar | None = None
        self.is_paste_sheet_open = False

        # Build real Inbox view
        self.inbox_view = InboxView(
            saves=saves,
            suggestions=suggestions,
            active_jobs=active_jobs,
            on_add_link=self.open_paste_sheet,
            on_refresh=self.refresh_inbox,
            on_accept_suggestion=self.handle_accept_suggestion,
            on_ignore_suggestion=self.handle_ignore_suggestion,
            theme_mode=theme_mode,
        )

        # Build App Shell hosting the Inbox view
        self.app_shell = AppShellLayout(
            inbox_view=self.inbox_view,
            on_add_link=self.open_paste_sheet,
            initial_tab=TAB_INBOX,
            theme_mode=theme_mode,
        )

        # Build Onboarding view
        self.onboarding_view = OnboardingView(
            on_finish=self.transition_to_shell,
            on_skip=self.transition_to_shell,
            on_persist_preference=self._persist_preference,
            theme_mode=theme_mode,
        )

        # Build Splash view
        self.splash_view = SplashView(
            on_complete=self.handle_splash_complete,
            has_seen_onboarding=has_seen_onboarding,
            theme_mode=theme_mode,
        )

        # Paste Sheet overlay container
        self.paste_sheet: AddLinkPasteSheet | None = None
        self.overlay_container = ft.Container(visible=False)

        # Root content switcher
        self.viewport = ft.Container(
            content=self.splash_view,
            expand=True,
        )

        super().__init__(
            content=ft.Stack(
                controls=[
                    self.viewport,
                    self.overlay_container,
                ],
                expand=True,
            ),
            expand=True,
        )

    def handle_splash_complete(self, has_seen_onboarding: bool) -> None:
        """Route from splash into onboarding (first run) or directly to shell."""
        if has_seen_onboarding:
            self.transition_to_shell()
        else:
            self.viewport.content = self.onboarding_view

    def transition_to_shell(self) -> None:
        """Route into the main AppShellLayout."""
        self.has_seen_onboarding = True
        self.viewport.content = self.app_shell

    def open_paste_sheet(self) -> None:
        """Open the AddLinkPasteSheet modal bottom sheet."""
        self.paste_sheet = AddLinkPasteSheet(
            on_submit=self.handle_capture_submit,
            on_cancel=self.close_paste_sheet,
            on_success=self.handle_capture_success,
            theme_mode=self.theme_mode_val,
        )
        self.overlay_container.content = self.paste_sheet
        self.overlay_container.visible = True
        self.is_paste_sheet_open = True

    def close_paste_sheet(self) -> None:
        """Dismiss the AddLinkPasteSheet modal."""
        self.overlay_container.visible = False
        self.overlay_container.content = None
        self.paste_sheet = None
        self.is_paste_sheet_open = False

    def handle_capture_submit(self, payload: dict[str, Any]) -> Any:
        """Handle submit action from paste sheet."""
        if self.on_save_capture is not None:
            return self.on_save_capture(payload)
        return {"id": "save-mock-id", "url": payload.get("url"), "status": "queued"}

    def handle_capture_success(self, save_data: dict[str, Any]) -> None:
        """Dismiss paste sheet and request inbox refresh on capture success."""
        self.close_paste_sheet()
        self.refresh_inbox()

    def refresh_inbox(self) -> None:
        """Request inbox data reload."""
        self.inbox_view.refresh()

    def handle_accept_suggestion(self, save_id: str, folder_path: str) -> None:
        """Trigger UndoSnackBar feedback upon accepting folder suggestion."""
        self.last_snackbar = UndoSnackBar(
            message=f"Moved to {folder_path}",
            duration_ms=UNDO_DURATION_MS,
            on_undo=lambda _: self.undo_suggestion_acceptance(save_id),
            theme_mode=self.theme_mode_val,
        )

    def handle_ignore_suggestion(self, save_id: str) -> None:
        """Trigger UndoSnackBar feedback upon ignoring suggestion."""
        self.last_snackbar = UndoSnackBar(
            message="Suggestion dismissed",
            duration_ms=UNDO_DURATION_MS,
            on_undo=lambda _: self.undo_suggestion_dismissal(save_id),
            theme_mode=self.theme_mode_val,
        )

    def undo_suggestion_acceptance(self, save_id: str) -> None:
        """Revert folder suggestion acceptance."""
        pass

    def undo_suggestion_dismissal(self, save_id: str) -> None:
        """Revert folder suggestion dismissal."""
        pass

    def _persist_preference(self, key: str, value: bool) -> None:
        """Persist user preference."""
        if key == "has_seen_onboarding":
            self.has_seen_onboarding = value
