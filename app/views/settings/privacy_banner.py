"""Privacy disclosure banner for ClayBank Settings.

Displays non-dismissible, transparent disclosures confirming videos are never
stored and only transcripts and metadata are processed by Cloud AI.
Derived from Docs/Phases.md Phase 7, Docs/Design.md §8, Docs/UIUX.md §11, and Prototype v2.
"""

from __future__ import annotations

import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    CARD_RADIUS,
    FONT_FAMILY_UI,
    FONT_SIZE_MUTED,
    SPACING_8,
    SPACING_12,
    SPACING_16,
)

PRIVACY_BANNER_TEXT = "Privacy: videos are never saved. Cloud AI gets the transcript and metadata only."


class PrivacyBanner(ft.Container):
    """Persistent privacy disclosure container for the Settings screen."""

    def __init__(
        self,
        *,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
        width: float | None = None,
    ) -> None:
        palette = get_palette(theme_mode)

        self.icon_control = ft.Icon(
            icon=ft.Icons.LOCK_OUTLINE_ROUNDED,
            size=18.0,
            color=palette["muted"],
        )

        self.text_control = ft.Text(
            value=PRIVACY_BANNER_TEXT,
            size=FONT_SIZE_MUTED,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
            expand=True,
        )

        content_row = ft.Row(
            controls=[
                self.icon_control,
                self.text_control,
            ],
            spacing=SPACING_12,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

        super().__init__(
            content=content_row,
            bgcolor=palette["card"],
            border=ft.Border.all(width=1.0, color=palette["line"]),
            border_radius=ft.BorderRadius.all(CARD_RADIUS),
            padding=ft.Padding.all(SPACING_12),
            width=width,
        )
