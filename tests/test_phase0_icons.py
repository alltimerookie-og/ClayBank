"""Unit tests for Phase 0 Step 2: Icon System."""

from __future__ import annotations

import flet as ft

from app.shell.icons import (
    ICON_SIZE_DEFAULT,
    ICON_SIZE_LARGE,
    ICON_SIZE_SMALL,
    IconName,
    get_icon,
)


def test_icon_sizes() -> None:
    """Verify icon dimension constants."""
    assert ICON_SIZE_SMALL == 18.0
    assert ICON_SIZE_DEFAULT == 22.0
    assert ICON_SIZE_LARGE == 48.0


def test_get_icon_enum_mapping() -> None:
    """Verify all canonical IconName values resolve to valid Flet Icon controls."""
    for icon_name in IconName:
        control = get_icon(icon_name)
        assert isinstance(control, ft.Icon)
        assert control.size == ICON_SIZE_DEFAULT
        assert control.icon is not None


def test_get_icon_string_case_insensitivity() -> None:
    """Verify string keys resolve correctly regardless of case."""
    control_lower = get_icon("inbox")
    control_upper = get_icon("INBOX")
    assert control_lower.icon == ft.Icons.INBOX_OUTLINED
    assert control_upper.icon == ft.Icons.INBOX_OUTLINED


def test_get_icon_custom_parameters() -> None:
    """Verify size, color, and tooltip parameter pass-through."""
    control = get_icon(
        IconName.CHAT,
        size=ICON_SIZE_SMALL,
        color="#B5532F",
        tooltip="Ask library",
    )
    assert control.icon == ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED
    assert control.size == 18.0
    assert control.color == "#B5532F"
    assert control.tooltip == "Ask library"


def test_get_icon_fallback() -> None:
    """Verify unknown icon name degrades safely to a fallback icon."""
    control = get_icon("non_existent_glyph")
    assert control.icon == ft.Icons.HELP_OUTLINE_ROUNDED

