"""Phase 8 Capture Surfaces and Notification package.

Contains the NotificationCoordinator state manager, notification drawer preview
component, and integration seams for foreground capture and share intents.
Derived from Docs/Phases.md Phase 8, Docs/Architecture.md §3.3, and Docs/Memory.md §5.
"""

from app.views.capture.notification_coordinator import (
    ACTION_OPEN_APP,
    ACTION_PASTE_AND_SAVE,
    ACTION_SHARE_TARGET,
    NOTIFICATION_BODY,
    NOTIFICATION_HEADER,
    NOTIFICATION_ID_PROGRESS,
    NOTIFICATION_ID_QUICK_SAVE,
    NOTIFICATION_TITLE,
    NotificationCoordinator,
)

__all__ = [
    "ACTION_OPEN_APP",
    "ACTION_PASTE_AND_SAVE",
    "ACTION_SHARE_TARGET",
    "NOTIFICATION_BODY",
    "NOTIFICATION_HEADER",
    "NOTIFICATION_ID_PROGRESS",
    "NOTIFICATION_ID_QUICK_SAVE",
    "NOTIFICATION_TITLE",
    "NotificationCoordinator",
]
