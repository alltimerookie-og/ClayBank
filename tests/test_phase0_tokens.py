"""Unit tests for Phase 0 Step 2: Typography and Spacing Tokens."""

from __future__ import annotations

import flet as ft

from app.shell.tokens import (
    BUTTON_RADIUS,
    CARD_RADIUS,
    FONT_FAMILY_MONO,
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_DISPLAY,
    FONT_SIZE_H1,
    FONT_SIZE_H2,
    FONT_SIZE_LABEL,
    FONT_SIZE_MICRO,
    FONT_SIZE_MONO,
    FONT_SIZE_MUTED,
    FONT_SIZE_TITLE,
    FONT_SIZE_TITLE_LARGE,
    MIN_TOUCH_TARGET,
    PILL_RADIUS,
    SECONDARY_RADIUS,
    SHEET_RADIUS,
    SPACING_2,
    SPACING_4,
    SPACING_6,
    SPACING_8,
    SPACING_10,
    SPACING_12,
    SPACING_14,
    SPACING_16,
    SPACING_18,
    SPACING_24,
    SPACING_32,
    THUMBNAIL_RADIUS,
    create_text_style,
)


def test_typography_font_families() -> None:
    """Verify standard UI and monospace font families."""
    assert "system-ui" in FONT_FAMILY_UI
    assert "monospace" in FONT_FAMILY_MONO


def test_typography_scale_hierarchy() -> None:
    """Verify font size scale matches design specifications."""
    assert FONT_SIZE_DISPLAY == 40.0
    assert FONT_SIZE_H1 == 26.0
    assert FONT_SIZE_H2 == 17.0
    assert FONT_SIZE_TITLE_LARGE == 18.0
    assert FONT_SIZE_TITLE == 15.0
    assert FONT_SIZE_BODY == 14.0
    assert FONT_SIZE_MUTED == 13.0
    assert FONT_SIZE_MONO == 12.5
    assert FONT_SIZE_MICRO == 12.0
    assert FONT_SIZE_LABEL == 11.0


def test_corner_radii() -> None:
    """Verify corner radii adhere to Design.md §4 rules."""
    assert CARD_RADIUS == 16.0
    assert SHEET_RADIUS == 24.0
    assert BUTTON_RADIUS == 14.0
    assert SECONDARY_RADIUS == 12.0
    assert THUMBNAIL_RADIUS == 12.0
    assert PILL_RADIUS == 999.0


def test_minimum_touch_target() -> None:
    """Verify minimum touch target floor is 44 px for accessibility."""
    assert MIN_TOUCH_TARGET >= 44.0


def test_spacing_scale() -> None:
    """Verify monotonic spacing scale definitions."""
    spacings = [
        SPACING_2,
        SPACING_4,
        SPACING_6,
        SPACING_8,
        SPACING_10,
        SPACING_12,
        SPACING_14,
        SPACING_16,
        SPACING_18,
        SPACING_24,
        SPACING_32,
    ]
    assert spacings == sorted(spacings)
    assert all(s > 0 for s in spacings)


def test_create_text_style_defaults() -> None:
    """Verify TextStyle creation with default token parameters."""
    style = create_text_style()
    assert isinstance(style, ft.TextStyle)
    assert style.font_family == FONT_FAMILY_UI
    assert style.size == FONT_SIZE_BODY
    assert style.weight == ft.FontWeight.NORMAL
    assert not style.italic


def test_create_text_style_monospace() -> None:
    """Verify TextStyle creation for monospace note source editing."""
    style = create_text_style(
        size=FONT_SIZE_MONO,
        is_mono=True,
        weight=ft.FontWeight.NORMAL,
    )
    assert style.font_family == FONT_FAMILY_MONO
    assert style.size == 12.5
