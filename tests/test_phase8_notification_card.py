"""Test suite for Phase 8 QuickSaveNotificationCard component.

Validates exact specification copy, action buttons, touch targets, job progress
transitions, preview labeling, and light/dark theme styling.
Derived from Docs/Phases.md Phase 8, Docs/Architecture.md §3.3, and
PrototypingFiles/Claybank_ Interactive Workflow v2.html Screen s12.
"""

from __future__ import annotations

from typing import Any
import flet as ft
import pytest

from app.shell.tokens import MIN_TOUCH_TARGET
from app.views.capture.notification_card import QuickSaveNotificationCard
from app.views.capture.notification_coordinator import (
    NOTIFICATION_BODY,
    NOTIFICATION_TITLE,
)


def _simulate_click(control: ft.Control) -> None:
    fn: Any = getattr(control, "on_click", None)
    assert callable(fn)
    fn(None)


class TestQuickSaveNotificationCard:
    """Tests for QuickSaveNotificationCard presentation and interactions."""

    def test_exact_copy_and_header(self) -> None:
        """Verify exact text, header, and preview labeling."""
        card = QuickSaveNotificationCard()

        assert card.header_text.value == "Claybank"
        assert card.time_text.value == "· now"
        assert card.title_text.value == NOTIFICATION_TITLE
        assert card.title_text.value == "Save a link"
        assert card.body_text.value == NOTIFICATION_BODY
        assert (
            card.body_text.value
            == "Copy a link, then tap Paste and save. Android opens the app first - clipboard reads there, not in the background."
        )

        # Preview badge verification
        assert isinstance(card.preview_badge.content, ft.Text)
        assert card.preview_badge.content.value == "Preview"

    def test_actions_and_minimum_touch_targets(self) -> None:
        """Verify Paste and save and Open app buttons with minimum 44 px touch targets."""
        card = QuickSaveNotificationCard()

        assert card.paste_save_btn.content == "Paste and save"
        assert card.paste_save_btn.height is not None
        assert card.paste_save_btn.height >= MIN_TOUCH_TARGET

        assert card.open_app_btn.content == "Open app"
        assert card.open_app_btn.height is not None
        assert card.open_app_btn.height >= MIN_TOUCH_TARGET

    def test_action_callbacks_invocation(self) -> None:
        """Verify clicking action buttons invokes respective callbacks."""
        paste_calls: list[bool] = []
        open_calls: list[bool] = []

        card = QuickSaveNotificationCard(
            on_paste_and_save=lambda: paste_calls.append(True),
            on_open_app=lambda: open_calls.append(True),
        )

        _simulate_click(card.paste_save_btn)
        assert paste_calls == [True]
        assert open_calls == []

        _simulate_click(card.open_app_btn)
        assert paste_calls == [True]
        assert open_calls == [True]

    def test_job_progress_state_transitions(self) -> None:
        """Verify card transitions between persistent quick-save and active job progress."""
        card = QuickSaveNotificationCard()
        assert card.body_text.visible == True
        assert card.actions_row.visible == True
        assert card.progress_section.visible == False

        # Transition to active job progress
        card.set_job_progress(
            title="Garlic bread recipe",
            step=2,
            total_steps=3,
            stage_name="Transcribing",
            progress=0.66,
        )

        assert card.title_text.value == "Saving: Garlic bread recipe"
        assert card.body_text.visible == False
        assert card.actions_row.visible == False
        assert card.progress_section.visible == True
        assert card.progress_subtitle.value == "Step 2 of 3: Transcribing"
        assert card.progress_bar.value == 0.66

        # Clear job progress reverts to quick-save
        card.clear_job_progress()
        assert card.title_text.value == NOTIFICATION_TITLE
        assert card.body_text.visible == True
        assert card.actions_row.visible == True
        assert card.progress_section.visible == False

    def test_dark_mode_rendering(self) -> None:
        """Verify dark mode theme rendering."""
        card = QuickSaveNotificationCard(theme_mode=ft.ThemeMode.DARK)
        assert card.bgcolor is not None
        assert card.header_text.color is not None
        assert card.title_text.color is not None
