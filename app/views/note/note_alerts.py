"""Alert and Confirmation Surfaces for ClayBank Item Notes.

Provides:
1. ConflictBanner: Triggered on 409 conflict, offering 'Keep Local' and 'Discard Local' recovery.
2. DeleteConfirmBar: Inline card with confirmation before note deletion and deleted state feedback.

Derived from Docs/Rules.md §5, Docs/UIUX.md §6, and Prototype v2 Screen 8.
"""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from app.shell.icons import IconName, get_icon
from app.shell.theme import get_palette
from app.shell.tokens import (
    CARD_RADIUS,
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_LABEL,
    MIN_TOUCH_TARGET,
    PILL_RADIUS,
    SPACING_8,
    SPACING_12,
    create_text_style,
)
from app.ui.card import ClayCard


class ConflictBanner(ClayCard):
    """Warning banner displayed when a stale-write 409 conflict occurs."""

    def __init__(
        self,
        *,
        on_keep_local: Callable[[], Any] | None = None,
        on_discard_local: Callable[[], Any] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.on_keep_local = on_keep_local
        self.on_discard_local = on_discard_local
        self.theme_mode_val = theme_mode

        palette = get_palette(theme_mode)

        self.message_text = ft.Text(
            "Conflict: this note was modified elsewhere. Keep your local edits or reload server version?",
            style=create_text_style(
                size=FONT_SIZE_LABEL,
                color=palette["accent_ink"],
                weight=ft.FontWeight.W_500,
            ),
            expand=True,
        )

        self.keep_button = ft.Container(
            content=ft.Text(
                "Keep Local",
                style=create_text_style(
                    size=FONT_SIZE_LABEL,
                    weight=ft.FontWeight.BOLD,
                    color=palette["accent_fg"],
                ),
            ),
            bgcolor=palette["accent"],
            padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
            border_radius=ft.BorderRadius.all(PILL_RADIUS),
            alignment=ft.Alignment(0, 0),
            height=36.0,
            on_click=lambda _: self.keep_local(),
        )

        self.discard_button = ft.Container(
            content=ft.Text(
                "Discard Local",
                style=create_text_style(
                    size=FONT_SIZE_LABEL,
                    weight=ft.FontWeight.W_500,
                    color=palette["ink"],
                ),
            ),
            bgcolor=palette["chip"],
            padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
            border_radius=ft.BorderRadius.all(PILL_RADIUS),
            alignment=ft.Alignment(0, 0),
            height=36.0,
            on_click=lambda _: self.discard_local(),
        )

        layout_row = ft.Row(
            controls=[
                self.message_text,
                self.keep_button,
                self.discard_button,
            ],
            spacing=SPACING_8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        super().__init__(
            content=layout_row,
            padding=SPACING_12,
            theme_mode=theme_mode,
        )
        self.bgcolor = palette["accent_bg"]
        self.border = ft.Border.all(1.0, palette["accent"])

    def keep_local(self) -> None:
        """User chose to preserve local version."""
        if self.on_keep_local is not None:
            self.on_keep_local()

    def discard_local(self) -> None:
        """User chose to reload server version."""
        if self.on_discard_local is not None:
            self.on_discard_local()


class DeleteConfirmBar(ClayCard):
    """Inline confirmation card for deleting a note and save."""

    def __init__(
        self,
        *,
        on_confirm_delete: Callable[[], Any] | None = None,
        on_cancel: Callable[[], Any] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.on_confirm_delete = on_confirm_delete
        self.on_cancel = on_cancel
        self.theme_mode_val = theme_mode

        self.is_deleted = False

        palette = get_palette(theme_mode)

        self.prompt_text = ft.Text(
            "Delete this note and its save?",
            style=create_text_style(
                size=FONT_SIZE_BODY,
                color=palette["ink"],
                weight=ft.FontWeight.W_500,
            ),
            expand=True,
        )

        self.delete_button = ft.Container(
            content=ft.Text(
                "Delete",
                style=create_text_style(
                    size=FONT_SIZE_LABEL,
                    weight=ft.FontWeight.BOLD,
                    color=palette["accent_fg"],
                ),
            ),
            bgcolor=palette["accent"],
            padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
            border_radius=ft.BorderRadius.all(PILL_RADIUS),
            alignment=ft.Alignment(0, 0),
            height=36.0,
            on_click=lambda _: self.confirm_delete(),
        )

        self.cancel_button = ft.Container(
            content=ft.Text(
                "Cancel",
                style=create_text_style(
                    size=FONT_SIZE_LABEL,
                    color=palette["ink"],
                ),
            ),
            bgcolor=palette["chip"],
            padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
            border_radius=ft.BorderRadius.all(PILL_RADIUS),
            alignment=ft.Alignment(0, 0),
            height=36.0,
            on_click=lambda _: self.cancel(),
        )

        self.buttons_row = ft.Row(
            controls=[
                self.delete_button,
                self.cancel_button,
            ],
            spacing=SPACING_8,
            tight=True,
        )

        layout_row = ft.Row(
            controls=[
                self.prompt_text,
                self.buttons_row,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=SPACING_8,
        )

        super().__init__(
            content=layout_row,
            padding=SPACING_12,
            theme_mode=theme_mode,
        )

    def confirm_delete(self) -> None:
        """Transition to deleted state and trigger callback."""
        self.is_deleted = True
        self.prompt_text.value = "This note is deleted."
        self.buttons_row.visible = False

        if self.on_confirm_delete is not None:
            self.on_confirm_delete()

    def reset_state(self) -> None:
        """Reset confirmation card back to initial prompt (e.g. after undo)."""
        self.is_deleted = False
        self.prompt_text.value = "Delete this note and its save?"
        self.buttons_row.visible = True

    def cancel(self) -> None:
        """Dismiss confirmation bar."""
        if self.on_cancel is not None:
            self.on_cancel()
