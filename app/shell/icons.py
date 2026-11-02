"""Icon system module mapping canonical ClayBank icons to Flet primitives.

Derived from Docs/Design.md §5 and Prototype v2 SVG definitions.
"""

from __future__ import annotations

from enum import StrEnum
import flet as ft

ICON_SIZE_SMALL = 18.0
ICON_SIZE_DEFAULT = 22.0
ICON_SIZE_LARGE = 48.0


class IconName(StrEnum):
    """Canonical icon identifiers used across the ClayBank UI."""

    INBOX = "inbox"
    FOLDER = "folder"
    SEARCH = "search"
    SETTINGS = "settings"
    GEAR = "gear"
    CHECK = "check"
    BACK = "back"
    PLAY = "play"
    TAGS = "tags"
    OVERFLOW = "overflow"
    CHAT = "chat"
    ADD = "add"


_ICON_MAP: dict[str, str] = {
    IconName.INBOX: ft.Icons.INBOX_OUTLINED,
    IconName.FOLDER: ft.Icons.FOLDER_OUTLINED,
    IconName.SEARCH: ft.Icons.SEARCH_ROUNDED,
    IconName.SETTINGS: ft.Icons.SETTINGS_OUTLINED,
    IconName.GEAR: ft.Icons.SETTINGS_OUTLINED,
    IconName.CHECK: ft.Icons.CHECK_ROUNDED,
    IconName.BACK: ft.Icons.ARROW_BACK_ROUNDED,
    IconName.PLAY: ft.Icons.PLAY_ARROW_ROUNDED,
    IconName.TAGS: ft.Icons.LOCAL_OFFER_OUTLINED,
    IconName.OVERFLOW: ft.Icons.MORE_HORIZ_ROUNDED,
    IconName.CHAT: ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED,
    IconName.ADD: ft.Icons.ADD_ROUNDED,
}


def get_icon(
    name: IconName | str,
    *,
    size: float = ICON_SIZE_DEFAULT,
    color: str | None = None,
    tooltip: str | None = None,
) -> ft.Icon:
    """Create a standardized Flet Icon control with proper dimensions and styling.

    Args:
        name: IconName enum value or string key.
        size: Icon size in pixels (defaults to 22 px).
        color: Optional hex or theme color string.
        tooltip: Optional tooltip for accessibility.

    Returns:
        Configured ft.Icon control.
    """
    key = name.value if isinstance(name, IconName) else str(name).lower()
    icon_glyph = _ICON_MAP.get(key, ft.Icons.HELP_OUTLINE_ROUNDED)
    return ft.Icon(
        icon=icon_glyph,
        size=size,
        color=color,
        tooltip=tooltip,
    )

