"""Test suite for Phase 8 NotificationCoordinator.

Validates the first-save permission gate, permission state transitions,
quick-save notification lifecycle, job progress notifications, duplicate
prevention, settings toggle interactions, and external intent routing.
Derived from Docs/Phases.md Phase 8, Docs/Architecture.md §3.3, and Docs/Memory.md §5.
"""

from __future__ import annotations

from typing import Any
import pytest

from app.views.capture.notification_coordinator import (
    ACTION_OPEN_APP,
    ACTION_PASTE_AND_SAVE,
    ACTION_SHARE_TARGET,
    NOTIFICATION_BODY,
    NOTIFICATION_HEADER,
    NOTIFICATION_ID_PROGRESS,
    NOTIFICATION_ID_QUICK_SAVE,
    NOTIFICATION_TITLE,
    PERMISSION_DENIED,
    PERMISSION_GRANTED,
    PERMISSION_NOT_REQUESTED,
    PERMISSION_UNAVAILABLE,
    NotificationCoordinator,
)


class TestNotificationCoordinator:
    """Tests for NotificationCoordinator state machine and lifecycle hooks."""

    def test_default_initial_state(self) -> None:
        """Verify coordinator defaults before any save or permission check."""
        coord = NotificationCoordinator()
        assert coord.is_supported is True
        assert coord.permission_state == PERMISSION_NOT_REQUESTED
        assert coord.has_completed_first_save is False
        assert coord.has_prompted_for_permission is False
        assert coord.quick_save_preference is True
        assert coord.is_notification_active is False
        assert coord.active_job_progress is None

    def test_no_permission_request_on_initialization(self) -> None:
        """Verify no permission callbacks are called on construction."""
        prompt_called = []

        coord = NotificationCoordinator(
            on_request_permission=lambda: prompt_called.append(True),
        )
        assert len(prompt_called) == 0
        assert coord.permission_state == PERMISSION_NOT_REQUESTED

    def test_first_save_permission_gate_with_preference_enabled(self) -> None:
        """First successful save triggers permission request when preference is True."""
        prompts: list[bool] = []
        posted: list[dict[str, Any]] = []

        def handle_permission() -> str:
            prompts.append(True)
            return PERMISSION_GRANTED

        def handle_post(payload: dict[str, Any]) -> bool:
            posted.append(payload)
            return True

        coord = NotificationCoordinator(
            on_request_permission=handle_permission,
            on_post_notification=handle_post,
        )

        # Execute first save
        triggered = coord.record_first_save_success(quick_save_preference=True)
        assert triggered is True
        assert len(prompts) == 1
        assert coord.has_completed_first_save is True
        assert coord.has_prompted_for_permission is True
        assert coord.permission_state == PERMISSION_GRANTED
        assert coord.is_notification_active is True

        # Verify posted payload matches exact specification
        assert len(posted) == 1
        p = posted[0]
        assert p["id"] == NOTIFICATION_ID_QUICK_SAVE
        assert p["header"] == NOTIFICATION_HEADER
        assert p["title"] == NOTIFICATION_TITLE
        assert p["body"] == NOTIFICATION_BODY
        assert p["actions"] == [
            {"id": ACTION_PASTE_AND_SAVE, "title": "Paste and save"},
            {"id": ACTION_OPEN_APP, "title": "Open app"},
        ]

    def test_first_save_with_preference_disabled_skips_permission(self) -> None:
        """If user turned off quick-save notification, first save must NOT prompt."""
        prompts: list[bool] = []

        coord = NotificationCoordinator(
            on_request_permission=lambda: prompts.append(True),
        )

        triggered = coord.record_first_save_success(quick_save_preference=False)
        assert triggered is False
        assert len(prompts) == 0
        assert coord.has_completed_first_save is True
        assert coord.has_prompted_for_permission is False
        assert coord.permission_state == PERMISSION_NOT_REQUESTED
        assert coord.is_notification_active is False

    def test_single_prompt_guard_no_repeated_prompts(self) -> None:
        """Subsequent saves must NEVER re-prompt for permission."""
        prompts: list[bool] = []

        coord = NotificationCoordinator(
            on_request_permission=lambda: prompts.append(True) or PERMISSION_GRANTED,
        )

        # First save prompts
        coord.record_first_save_success()
        assert len(prompts) == 1

        # Second save does NOT prompt
        coord.record_first_save_success()
        assert len(prompts) == 1

        # Third save does NOT prompt
        coord.record_first_save_success()
        assert len(prompts) == 1

    def test_permission_denied_behavior(self) -> None:
        """Permission denial transitions state and does not post notification."""
        posted: list[dict[str, Any]] = []

        coord = NotificationCoordinator(
            on_request_permission=lambda: PERMISSION_DENIED,
            on_post_notification=lambda p: posted.append(p) or True,
        )

        triggered = coord.record_first_save_success()
        assert triggered is False
        assert coord.permission_state == PERMISSION_DENIED
        assert coord.is_notification_active is False
        assert len(posted) == 0

    def test_unsupported_platform_graceful_degradation(self) -> None:
        """When platform notification support is unavailable, coordinator degrades gracefully."""
        coord = NotificationCoordinator(is_supported=False)

        triggered = coord.record_first_save_success()
        assert triggered is False
        assert coord.permission_state == PERMISSION_UNAVAILABLE
        assert coord.is_notification_active is False

    def test_settings_toggle_dismiss_and_restore(self) -> None:
        """Toggling preference in Settings dismisses or re-posts the notification."""
        posted: list[dict[str, Any]] = []
        dismissed: list[int] = []

        coord = NotificationCoordinator(
            initial_permission_state=PERMISSION_GRANTED,
            on_post_notification=lambda p: posted.append(p) or True,
            on_dismiss_notification=lambda nid: dismissed.append(nid) or True,
        )
        coord.post_quick_save_notification()
        assert coord.is_notification_active
        assert len(posted) == 1

        # Toggle off in settings
        coord.set_quick_save_preference(False)
        assert not coord.quick_save_preference
        assert not coord.is_notification_active
        assert dismissed == [NOTIFICATION_ID_QUICK_SAVE]

        # Toggle back on
        coord.set_quick_save_preference(True)
        assert coord.quick_save_preference
        assert coord.is_notification_active
        assert len(posted) == 2

    def test_settings_toggle_on_after_denial_does_not_silently_reprompt(self) -> None:
        """Enabling setting after permission was denied must respect denied state."""
        prompts: list[bool] = []

        coord = NotificationCoordinator(
            initial_permission_state=PERMISSION_DENIED,
            has_completed_first_save=True,
            has_prompted_for_permission=True,
            on_request_permission=lambda: prompts.append(True),
        )

        coord.set_quick_save_preference(True)
        assert len(prompts) == 0
        assert coord.permission_state == PERMISSION_DENIED
        assert coord.is_notification_active is False

    def test_job_progress_notification_lifecycle(self) -> None:
        """Coordinator manages active save job progress notifications."""
        posted: list[dict[str, Any]] = []
        dismissed: list[int] = []

        coord = NotificationCoordinator(
            initial_permission_state=PERMISSION_GRANTED,
            on_post_notification=lambda p: posted.append(p) or True,
            on_dismiss_notification=lambda nid: dismissed.append(nid) or True,
        )

        # Post progress
        ok = coord.update_job_progress(
            job_id="job-123",
            title="Creamy garlic pasta",
            step=2,
            total_steps=3,
            stage_name="Transcribing",
            progress=0.66,
        )
        assert ok is True
        assert len(posted) == 1
        p = posted[0]
        assert p["id"] == NOTIFICATION_ID_PROGRESS
        assert p["title"] == "Saving: Creamy garlic pasta"
        assert p["subtitle"] == "Step 2 of 3: Transcribing"
        assert p["progress"] == 0.66
        assert coord.active_job_progress == p

        # Dismiss progress upon completion
        dismiss_ok = coord.dismiss_job_progress("job-123")
        assert dismiss_ok is True
        assert dismissed == [NOTIFICATION_ID_PROGRESS]
        assert coord.active_job_progress is None

    def test_external_capture_action_dispatch(self) -> None:
        """Incoming capture intents dispatch to external capture listener."""
        actions: list[tuple[str, str | None]] = []

        def handle_ext(action: str, url: str | None) -> None:
            actions.append((action, url))

        coord = NotificationCoordinator(on_external_capture=handle_ext)

        # Paste and save intent
        coord.handle_capture_action(ACTION_PASTE_AND_SAVE)
        assert actions == [(ACTION_PASTE_AND_SAVE, None)]

        # Share target intent with URL
        coord.handle_capture_action(ACTION_SHARE_TARGET, "https://youtube.com/watch?v=123")
        assert actions[-1] == (ACTION_SHARE_TARGET, "https://youtube.com/watch?v=123")

        # Open app intent
        coord.handle_capture_action(ACTION_OPEN_APP)
        assert actions[-1] == (ACTION_OPEN_APP, None)

    def test_error_resilience_preserves_state(self) -> None:
        """Callback exceptions do not crash coordinator or corrupt state."""
        errors: list[str] = []

        def failing_post(payload: dict[str, Any]) -> bool:
            raise RuntimeError("NotificationManager service dead")

        coord = NotificationCoordinator(
            initial_permission_state=PERMISSION_GRANTED,
            on_post_notification=failing_post,
            on_notification_error=lambda msg: errors.append(msg),
        )

        ok = coord.post_quick_save_notification()
        assert ok is False
        assert coord.is_notification_active is False
        assert len(errors) == 1
        assert "NotificationManager service dead" in errors[0]
