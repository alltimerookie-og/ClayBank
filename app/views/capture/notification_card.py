"""Visual representation of Phase 8 notification drawer card.

Provides an accessible, interactive Flet component representing the persistent
'Save a link' notification and active job progress notification from Prototype v2 §7(x).
Derived from Docs/Phases.md Phase 8, Docs/Architecture.md §3.3, and
PrototypingFiles/Claybank_ Interactive Workflow v2.html Screen s12.
"""

from __future__ import annotations

from typing import Any, Callable

import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    CARD_RADIUS,
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_MICRO,
    FONT_SIZE_MUTED,
    MIN_TOUCH_TARGET,
    PILL_RADIUS,
    SPACING_4,
    SPACING_6,
    SPACING_8,
    SPACING_10,
    SPACING_12,
    SPACING_16,
)
from app.ui.card import ClayCard
from app.views.capture.notification_coordinator import (
    NOTIFICATION_BODY,
    NOTIFICATION_HEADER,
    NOTIFICATION_TITLE,
)


class QuickSaveNotificationCard(ClayCard):
    """Visual representation of the persistent Quick-Save system notification card."""

    def __init__(
        self,
        *,
        on_paste_and_save: Callable[[], None] | None = None,
        on_open_app: Callable[[], None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.on_paste_and_save = on_paste_and_save
        self.on_open_app = on_open_app
        self.theme_mode_val = theme_mode

        palette = get_palette(theme_mode)

        # Header: Claybank · now  [Preview Badge]
        self.header_text = ft.Text(
            value="Claybank",
            size=FONT_SIZE_MUTED,
            weight=ft.FontWeight.W_600,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
        )
        self.time_text = ft.Text(
            value="· now",
            size=FONT_SIZE_MICRO,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
        )
        self.preview_badge = ft.Container(
            content=ft.Text(
                value="Preview",
                size=FONT_SIZE_MICRO,
                weight=ft.FontWeight.W_500,
                color=palette["muted"],
                font_family=FONT_FAMILY_UI,
            ),
            border=ft.Border.all(width=1.0, color=palette["line"]),
            border_radius=ft.BorderRadius.all(PILL_RADIUS),
            padding=ft.Padding.symmetric(horizontal=SPACING_6, vertical=2),
        )

        header_row = ft.Row(
            controls=[
                self.header_text,
                self.time_text,
                ft.Container(expand=True),
                self.preview_badge,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Main Title: Save a link
        self.title_text = ft.Text(
            value=NOTIFICATION_TITLE,
            size=FONT_SIZE_BODY,
            weight=ft.FontWeight.W_600,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
        )

        # Body: Copy a link, then tap Paste and save...
        self.body_text = ft.Text(
            value=NOTIFICATION_BODY,
            size=FONT_SIZE_MUTED,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
        )

        # Buttons: Paste and save & Open app
        self.paste_save_btn = ft.FilledButton(
            "Paste and save",
            on_click=lambda _: self._handle_paste_and_save(),
            style=ft.ButtonStyle(
                color=palette["accent_fg"],
                bgcolor=palette["accent"],
                shape=ft.RoundedRectangleBorder(radius=PILL_RADIUS),
                padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
            ),
            height=MIN_TOUCH_TARGET,
        )

        self.open_app_btn = ft.OutlinedButton(
            "Open app",
            on_click=lambda _: self._handle_open_app(),
            style=ft.ButtonStyle(
                color=palette["ink"],
                side=ft.BorderSide(width=1.0, color=palette["line"]),
                shape=ft.RoundedRectangleBorder(radius=PILL_RADIUS),
                padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
            ),
            height=MIN_TOUCH_TARGET,
        )

        self.actions_row = ft.Row(
            controls=[self.paste_save_btn, self.open_app_btn],
            spacing=SPACING_8,
        )

        # Job progress section (hidden by default)
        self.progress_subtitle = ft.Text(
            value="Step 2 of 3: Transcribing",
            size=FONT_SIZE_MICRO,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
        )
        self.progress_bar = ft.ProgressBar(
            value=0.5,
            color=palette["accent"],
            bgcolor=palette["accent_bg"],
            height=4,
        )
        self.progress_section = ft.Column(
            controls=[self.progress_subtitle, self.progress_bar],
            spacing=SPACING_4,
            visible=False,
        )

        super().__init__(
            content=ft.Column(
                controls=[
                    header_row,
                    self.title_text,
                    self.body_text,
                    self.actions_row,
                    self.progress_section,
                ],
                spacing=SPACING_8,
            ),
            padding=SPACING_12,
            theme_mode=theme_mode,
        )

    def _handle_paste_and_save(self) -> None:
        if self.on_paste_and_save is not None:
            self.on_paste_and_save()

    def _handle_open_app(self) -> None:
        if self.on_open_app is not None:
            self.on_open_app()

    def set_job_progress(
        self,
        title: str,
        step: int,
        total_steps: int = 3,
        stage_name: str = "Transcribing",
        progress: float | None = None,
    ) -> None:
        """Switch card to active job progress representation."""
        self.title_text.value = f"Saving: {title}"
        self.body_text.visible = False
        self.actions_row.visible = False

        self.progress_subtitle.value = f"Step {step} of {total_steps}: {stage_name}"
        self.progress_bar.value = progress
        self.progress_section.visible = True

    def clear_job_progress(self) -> None:
        """Revert card to persistent 'Save a link' representation."""
        self.title_text.value = NOTIFICATION_TITLE
        self.body_text.visible = True
        self.actions_row.visible = True
        self.progress_section.visible = False
