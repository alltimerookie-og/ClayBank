"""Tag Editor Bottom Sheet for ClayBank Item Notes.

Modal bottom sheet allowing users to view current tags, delete tags via '×' affordance,
and add new tags with normalization (leading '#' formatting, whitespace trimming, and duplicate check).

Derived from Docs/UIUX.md §6, Docs/api/schemas/tags-put.json, and Prototype v2 Screen 8.
"""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_LABEL,
    FONT_SIZE_TITLE_LARGE,
    MIN_TOUCH_TARGET,
    PILL_RADIUS,
    SPACING_8,
    SPACING_12,
    SPACING_16,
    create_text_style,
)
from app.ui.card import ClaySheet
from app.ui.chips import TagChip


class TagEditorSheet(ClaySheet):
    """Modal bottom sheet for modifying tags assigned to a save."""

    def __init__(
        self,
        *,
        current_tags: list[str] | None = None,
        on_save_tags: Callable[[list[str]], Any] | None = None,
        on_cancel: Callable[[], Any] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        raw_tags = current_tags or []
        self.tags_list: list[str] = [
            t.lstrip("#").strip() for t in raw_tags if str(t).strip()
        ]
        self.on_save_tags = on_save_tags
        self.on_cancel = on_cancel
        self.theme_mode_val = theme_mode

        palette = get_palette(theme_mode)

        # Title
        self.title_text = ft.Text(
            "Tags",
            style=create_text_style(
                size=FONT_SIZE_TITLE_LARGE,
                weight=ft.FontWeight.BOLD,
                color=palette["ink"],
            ),
        )

        # Tag chips container
        self.tags_row = ft.Row(
            controls=[],
            wrap=True,
            spacing=SPACING_8,
        )

        # Input field for new tag
        self.tag_input = ft.TextField(
            hint_text="add a tag…",
            text_size=FONT_SIZE_BODY,
            bgcolor=palette["background"],
            border_color=palette["line"],
            focused_border_color=palette["accent"],
            content_padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
            expand=True,
            on_submit=lambda _: self.add_tag(),
        )

        # Add button
        self.add_button = ft.Container(
            content=ft.Text(
                "Add",
                style=create_text_style(
                    size=FONT_SIZE_LABEL,
                    weight=ft.FontWeight.BOLD,
                    color=palette["ink"],
                ),
            ),
            padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
            bgcolor=palette["chip"],
            border_radius=ft.BorderRadius.all(PILL_RADIUS),
            alignment=ft.Alignment(0, 0),
            height=MIN_TOUCH_TARGET,
            on_click=lambda _: self.add_tag(),
        )

        input_row = ft.Row(
            controls=[
                self.tag_input,
                self.add_button,
            ],
            spacing=SPACING_8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Done button
        self.done_button = ft.FilledButton(
            "Done",
            style=ft.ButtonStyle(
                bgcolor=palette["accent"],
                color=palette["accent_fg"],
            ),
            height=MIN_TOUCH_TARGET,
            on_click=lambda _: self.done(),
        )

        # Cancel button
        self.cancel_button = ft.TextButton(
            "Cancel",
            style=ft.ButtonStyle(color=palette["muted"]),
            height=MIN_TOUCH_TARGET,
            on_click=lambda _: self.cancel(),
        )

        bottom_row = ft.Row(
            controls=[
                self.cancel_button,
                ft.Container(expand=True),
                self.done_button,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self._rebuild_tag_chips()

        sheet_content = ft.Column(
            controls=[
                self.title_text,
                ft.Container(height=SPACING_8),
                self.tags_row,
                ft.Container(height=SPACING_12),
                input_row,
                ft.Container(height=SPACING_16),
                bottom_row,
            ],
            tight=True,
            spacing=0,
        )

        super().__init__(
            content=sheet_content,
            theme_mode=theme_mode,
        )

    def _rebuild_tag_chips(self) -> None:
        """Construct TagChip widgets with delete affordance."""
        palette = get_palette(self.theme_mode_val)

        if not self.tags_list:
            self.tags_row.controls = [
                ft.Text(
                    "(No tags added)",
                    style=create_text_style(size=FONT_SIZE_LABEL, color=palette["muted"]),
                )
            ]
            return

        chips: list[ft.Control] = []
        for tag in self.tags_list:
            chips.append(
                TagChip(
                    name=f"{tag} ×",
                    on_click=lambda _, t=tag: self.remove_tag(t),
                    theme_mode=self.theme_mode_val,
                )
            )

        self.tags_row.controls = chips

    def add_tag(self) -> None:
        """Normalize, validate, and append new tag from input field."""
        raw_val = (self.tag_input.value or "").strip()
        if not raw_val:
            return

        normalized = raw_val.lstrip("#").strip()
        if normalized and normalized not in self.tags_list:
            self.tags_list.append(normalized)
            self._rebuild_tag_chips()

        self.tag_input.value = ""

    def remove_tag(self, tag: str) -> None:
        """Remove a tag from the current list."""
        if tag in self.tags_list:
            self.tags_list.remove(tag)
            self._rebuild_tag_chips()

    def done(self) -> None:
        """Confirm tag modifications and dispatch callback."""
        if self.on_save_tags is not None:
            self.on_save_tags(list(self.tags_list))

    def cancel(self) -> None:
        """Dismiss without applying changes."""
        if self.on_cancel is not None:
            self.on_cancel()

