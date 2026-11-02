"""Integration tests for Phase 2: Capture + Inbox Shell."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import pytest

from app.app import ClayBankApp
from app.shell.nav import TAB_INBOX
from app.ui.snackbar import UndoSnackBar

FIXTURES_PATH = Path("Docs/api/fixtures")


def test_app_lifecycle_splash_to_onboarding_to_shell() -> None:
    """Verify application routes from Splash -> Onboarding -> AppShell on fresh install."""
    app = ClayBankApp(has_seen_onboarding=False)

    # Initial view is SplashView
    assert app.viewport.content is app.splash_view

    # Warmup finishes -> routes to OnboardingView
    app.splash_view.finish_warmup()
    assert app.viewport.content is app.onboarding_view

    # User finishes or skips onboarding -> routes to AppShellLayout
    app.onboarding_view.skip()
    assert app.viewport.content is app.app_shell
    assert app.has_seen_onboarding is True
    assert app.app_shell.selected_index == TAB_INBOX


def test_app_lifecycle_splash_to_shell_when_returning_user() -> None:
    """Verify application routes directly from Splash -> AppShell when onboarding completed."""
    app = ClayBankApp(has_seen_onboarding=True)

    assert app.viewport.content is app.splash_view

    app.splash_view.finish_warmup()
    assert app.viewport.content is app.app_shell
    assert app.app_shell.selected_index == TAB_INBOX


def test_app_open_and_close_paste_sheet() -> None:
    """Verify opening and closing AddLinkPasteSheet modal."""
    app = ClayBankApp(has_seen_onboarding=True)
    app.splash_view.finish_warmup()

    assert app.is_paste_sheet_open is False
    assert app.overlay_container.visible is False

    # Open paste sheet
    app.open_paste_sheet()
    assert app.is_paste_sheet_open is True
    assert app.overlay_container.visible is True
    assert app.paste_sheet is not None

    # Close paste sheet
    app.close_paste_sheet()
    assert app.is_paste_sheet_open is False
    assert app.overlay_container.visible is False
    assert app.paste_sheet is None


def test_app_capture_success_refreshes_inbox() -> None:
    """Verify successful link capture dismisses sheet and triggers inbox refresh."""
    refreshed = False

    def mock_capture(payload: dict[str, Any]) -> dict[str, Any]:
        return {"id": "new-save-123", "url": payload["url"], "status": "queued"}

    app = ClayBankApp(
        has_seen_onboarding=True,
        on_save_capture=mock_capture,
    )
    app.splash_view.finish_warmup()

    # Track inbox refresh
    orig_refresh = app.inbox_view.refresh
    def tracked_refresh() -> None:
        nonlocal refreshed
        refreshed = True
        orig_refresh()

    app.inbox_view.on_refresh = tracked_refresh

    app.open_paste_sheet()
    assert app.paste_sheet is not None
    app.paste_sheet.url_field.value = "https://example.com/new-article"
    app.paste_sheet.submit()

    assert app.is_paste_sheet_open is False
    assert refreshed is True


def test_app_suggestion_accept_triggers_5s_undo_snackbar() -> None:
    """Verify accepting folder suggestion launches UndoSnackBar with 5000ms duration."""
    app = ClayBankApp(has_seen_onboarding=True)
    app.splash_view.finish_warmup()

    app.handle_accept_suggestion("save-123", "Reading / Articles")

    assert app.last_snackbar is not None
    assert isinstance(app.last_snackbar, UndoSnackBar)
    assert app.last_snackbar.duration == 5000
    assert "Moved to Reading / Articles" in app.last_snackbar.message_text


def test_app_suggestion_ignore_triggers_5s_undo_snackbar() -> None:
    """Verify ignoring suggestion launches UndoSnackBar with 5000ms duration."""
    app = ClayBankApp(has_seen_onboarding=True)
    app.splash_view.finish_warmup()

    app.handle_ignore_suggestion("save-456")

    assert app.last_snackbar is not None
    assert isinstance(app.last_snackbar, UndoSnackBar)
    assert app.last_snackbar.duration == 5000
    assert "Suggestion dismissed" in app.last_snackbar.message_text
