"""Typography, spacing, radius, and accessibility dimension tokens.

Derived directly from Docs/Design.md, Docs/Rules.md, and Prototype v2.
"""

from __future__ import annotations

import flet as ft

# ---------------------------------------------------------------------------
# Typography System
# ---------------------------------------------------------------------------

FONT_FAMILY_UI = "system-ui, sans-serif"
FONT_FAMILY_MONO = "ui-monospace, monospace"

# Size scale in density-independent pixels
FONT_SIZE_DISPLAY = 40.0
FONT_SIZE_H1 = 26.0
FONT_SIZE_H2 = 17.0
FONT_SIZE_TITLE_LARGE = 18.0
FONT_SIZE_TITLE = 15.0
FONT_SIZE_BODY = 14.0
FONT_SIZE_MUTED = 13.0
FONT_SIZE_MONO = 12.5
FONT_SIZE_MICRO = 12.0
FONT_SIZE_LABEL = 11.0

# Standard line heights
LINE_HEIGHT_DISPLAY = 1.1
LINE_HEIGHT_HEADING = 1.25
LINE_HEIGHT_BODY = 1.55
LINE_HEIGHT_MONO = 1.5

# ---------------------------------------------------------------------------
# Spacing Scale
# ---------------------------------------------------------------------------

SPACING_2 = 2.0
SPACING_4 = 4.0
SPACING_6 = 6.0
SPACING_8 = 8.0
SPACING_10 = 10.0
SPACING_12 = 12.0
SPACING_14 = 14.0
SPACING_16 = 16.0
SPACING_18 = 18.0
SPACING_24 = 24.0
SPACING_32 = 32.0

# ---------------------------------------------------------------------------
# Corner Radii
# ---------------------------------------------------------------------------

# Rounded cards are 16 px; bottom sheets are 24 px; buttons are 14 px
CARD_RADIUS = 16.0
SHEET_RADIUS = 24.0
BUTTON_RADIUS = 14.0
SECONDARY_RADIUS = 12.0
THUMBNAIL_RADIUS = 12.0
PILL_RADIUS = 999.0

# ---------------------------------------------------------------------------
# Accessibility & Interaction Dimensions
# ---------------------------------------------------------------------------

# Minimum touch target size for interactive touch surfaces (WCAG 2.5.5 / Design.md §9)
MIN_TOUCH_TARGET = 44.0


def create_text_style(
    *,
    size: float = FONT_SIZE_BODY,
    weight: ft.FontWeight = ft.FontWeight.NORMAL,
    color: str | None = None,
    italic: bool = False,
    is_mono: bool = False,
    line_height: float | None = None,
) -> ft.TextStyle:
    """Create a standardized Flet TextStyle adhering to ClayBank tokens."""
    return ft.TextStyle(
        font_family=FONT_FAMILY_MONO if is_mono else FONT_FAMILY_UI,
        size=size,
        weight=weight,
        color=color,
        italic=italic,
        height=line_height,
    )
