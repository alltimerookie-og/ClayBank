"""Notification lifecycle coordinator for ClayBank Phase 8.

Manages notification permission state, first-save permission gate, persistent
quick-save notification lifecycle, job progress states, and external capture intent
routing. Derived from Docs/Phases.md Phase 8, Docs/Architecture.md §3.3,
Docs/Memory.md §5, and Docs/db/0003_device.sql.
"""

from __future__ import annotations

from typing import Any, Callable

NOTIFICATION_ID_QUICK_SAVE = 1001
NOTIFICATION_ID_PROGRESS = 1002

NOTIFICATION_HEADER = "Claybank · now"
NOTIFICATION_TITLE = "Save a link"
NOTIFICATION_BODY = (
    "Copy a link, then tap Paste and save. Android opens the app first - "
    "clipboard reads there, not in the background."
)

ACTION_PASTE_AND_SAVE = "paste_and_save"
ACTION_OPEN_APP = "open_app"
ACTION_SHARE_TARGET = "share_target"

PERMISSION_NOT_REQUESTED = "not_requested"
PERMISSION_GRANTED = "granted"
PERMISSION_DENIED = "denied"
PERMISSION_UNAVAILABLE = "unavailable"


class NotificationCoordinator:
    """Coordinates notification permission state, lifecycle, and external capture intents."""

    def __init__(
        self,
        *,
        is_supported: bool = True,
        initial_permission_state: str = PERMISSION_NOT_REQUESTED,
        has_completed_first_save: bool = False,
        has_prompted_for_permission: bool = False,
        quick_save_preference: bool = True,
        on_request_permission: Callable[[], Any] | None = None,
        on_post_notification: Callable[[dict[str, Any]], bool] | None = None,
        on_dismiss_notification: Callable[[int], bool] | None = None,
        on_first_save_completed: Callable[[], None] | None = None,
        on_notification_error: Callable[[str], None] | None = None,
        on_external_capture: Callable[[str, str | None], None] | None = None,
    ) -> None:
        self._is_supported = is_supported
        self._permission_state = initial_permission_state
        self._has_completed_first_save = has_completed_first_save
        self._has_prompted_for_permission = has_prompted_for_permission
        self._quick_save_preference = quick_save_preference

        self.on_request_permission = on_request_permission
        self.on_post_notification = on_post_notification
        self.on_dismiss_notification = on_dismiss_notification
        self.on_first_save_completed = on_first_save_completed
        self.on_notification_error = on_notification_error
        self.on_external_capture = on_external_capture

        self._is_notification_active: bool = False
        self._active_job_progress: dict[str, Any] | None = None

    @property
    def is_supported(self) -> bool:
        """Whether native notifications are supported on the current platform."""
        return self._is_supported

    @property
    def permission_state(self) -> str:
        """Current runtime notification permission state."""
        return self._permission_state

    @property
    def has_completed_first_save(self) -> bool:
        """Whether user has completed at least one successful link save."""
        return self._has_completed_first_save

    @property
    def has_prompted_for_permission(self) -> bool:
        """Whether runtime permission prompt has already been requested."""
        return self._has_prompted_for_permission

    @property
    def quick_save_preference(self) -> bool:
        """User preference toggle state for quick-save notification."""
        return self._quick_save_preference

    @property
    def is_notification_active(self) -> bool:
        """Whether the persistent quick-save notification is currently posted."""
        return self._is_notification_active

    @property
    def active_job_progress(self) -> dict[str, Any] | None:
        """Current job progress notification data if active."""
        return self._active_job_progress

    def record_first_save_success(self, quick_save_preference: bool | None = None) -> bool:
        """Process successful save completion. Enforces the first-save permission gate.

        Returns True if a permission request was initiated, False otherwise.
        """
        is_first = not self._has_completed_first_save
        self._has_completed_first_save = True

        if quick_save_preference is not None:
            self._quick_save_preference = quick_save_preference

        if is_first and self.on_first_save_completed is not None:
            try:
                self.on_first_save_completed()
            except Exception as err:
                self._handle_error(f"Error in on_first_save_completed: {err}")

        # Permission gate conditions:
        # 1. Must be first prompt (never prompt repeatedly automatically)
        # 2. Preference must be enabled
        # 3. Permission must be 'not_requested'
        # 4. Native notifications must be supported
        if self._has_prompted_for_permission:
            return False

        if not self._quick_save_preference:
            return False

        if self._permission_state != PERMISSION_NOT_REQUESTED:
            return False

        if not self._is_supported:
            self._permission_state = PERMISSION_UNAVAILABLE
            return False

        # Request permission
        state = self.request_permission()
        return state == PERMISSION_GRANTED

    def request_permission(self) -> str:
        """Explicitly request OS notification permission through runtime callback."""
        self._has_prompted_for_permission = True

        if not self._is_supported or self.on_request_permission is None:
            self._permission_state = PERMISSION_UNAVAILABLE
            return PERMISSION_UNAVAILABLE

        try:
            res = self.on_request_permission()
            if res is True or res == PERMISSION_GRANTED:
                self._permission_state = PERMISSION_GRANTED
                if self._quick_save_preference:
                    self.post_quick_save_notification()
            elif res is False or res == PERMISSION_DENIED:
                self._permission_state = PERMISSION_DENIED
            elif res == PERMISSION_UNAVAILABLE:
                self._permission_state = PERMISSION_UNAVAILABLE
            else:
                self._permission_state = PERMISSION_DENIED
        except Exception as err:
            self._handle_error(f"Permission request failure: {err}")
            self._permission_state = PERMISSION_DENIED

        return self._permission_state

    def set_quick_save_preference(self, enabled: bool) -> None:
        """Reactively handle user preference changes from Settings."""
        self._quick_save_preference = enabled

        if not enabled:
            self.dismiss_quick_save_notification()
        else:
            if self._permission_state == PERMISSION_GRANTED and self._is_supported:
                self.post_quick_save_notification()
            elif (
                self._permission_state == PERMISSION_NOT_REQUESTED
                and self._has_completed_first_save
                and self._is_supported
            ):
                self.request_permission()

    def post_quick_save_notification(self) -> bool:
        """Post or update the persistent quick-save notification in the system shade."""
        if not self._is_supported:
            return False

        if self._permission_state != PERMISSION_GRANTED:
            return False

        payload = {
            "id": NOTIFICATION_ID_QUICK_SAVE,
            "channel_id": "claybank_quick_save",
            "header": NOTIFICATION_HEADER,
            "title": NOTIFICATION_TITLE,
            "body": NOTIFICATION_BODY,
            "actions": [
                {"id": ACTION_PASTE_AND_SAVE, "title": "Paste and save"},
                {"id": ACTION_OPEN_APP, "title": "Open app"},
            ],
            "ongoing": True,
            "sticky": True,
        }

        if self.on_post_notification is not None:
            try:
                ok = self.on_post_notification(payload)
                self._is_notification_active = ok
                return ok
            except Exception as err:
                self._handle_error(f"Failed to post quick-save notification: {err}")
                self._is_notification_active = False
                return False

        self._is_notification_active = True
        return True

    def dismiss_quick_save_notification(self) -> bool:
        """Dismiss the persistent quick-save notification."""
        self._is_notification_active = False

        if self.on_dismiss_notification is not None:
            try:
                return self.on_dismiss_notification(NOTIFICATION_ID_QUICK_SAVE)
            except Exception as err:
                self._handle_error(f"Failed to dismiss notification: {err}")
                return False

        return True

    def update_job_progress(
        self,
        job_id: str,
        title: str,
        step: int,
        total_steps: int = 3,
        stage_name: str = "Transcribing",
        progress: float | None = None,
    ) -> bool:
        """Update or post the active save-progress notification."""
        if not self._is_supported or self._permission_state != PERMISSION_GRANTED:
            return False

        payload = {
            "id": NOTIFICATION_ID_PROGRESS,
            "job_id": job_id,
            "channel_id": "claybank_progress",
            "header": NOTIFICATION_HEADER,
            "title": f"Saving: {title}",
            "subtitle": f"Step {step} of {total_steps}: {stage_name}",
            "progress": progress,
            "ongoing": True,
        }
        self._active_job_progress = payload

        if self.on_post_notification is not None:
            try:
                return self.on_post_notification(payload)
            except Exception as err:
                self._handle_error(f"Failed to post progress notification: {err}")
                return False

        return True

    def dismiss_job_progress(self, job_id: str | None = None) -> bool:
        """Dismiss the active save-progress notification."""
        self._active_job_progress = None

        if self.on_dismiss_notification is not None:
            try:
                return self.on_dismiss_notification(NOTIFICATION_ID_PROGRESS)
            except Exception as err:
                self._handle_error(f"Failed to dismiss progress notification: {err}")
                return False

        return True

    def handle_capture_action(self, action: str, url: str | None = None) -> None:
        """Process incoming external intent or notification action."""
        if self.on_external_capture is not None:
            try:
                self.on_external_capture(action, url)
            except Exception as err:
                self._handle_error(f"Error handling capture action {action}: {err}")

    def _handle_error(self, message: str) -> None:
        """Forward internal error to listener if registered."""
        if self.on_notification_error is not None:
            try:
                self.on_notification_error(message)
            except Exception:
                pass
