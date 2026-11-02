"""Folder Filing Bottom Sheet for ClayBank Item Notes.

Searchable bottom sheet modal allowing filing a save to an existing folder or unfiling to Inbox.
Filters folder options in real-time, highlights the currently selected folder, and validates
maximum folder depth (depth <= 3).

Derived from Docs/Design.md §7.3, Docs/UIUX.md §6, and Prototype v2 Screen 8.
"""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_TITLE_LARGE,
    MIN_TOUCH_TARGET,
    PILL_RADIUS,
    SPACING_8,
    SPACING_12,
    SPACING_16,
    create_text_style,
)
from app.ui.card import ClaySheet
from app.ui.chips import FolderChip

DEFAULT_FOLDERS: list[str] = [
    "Cooking / Pasta",
    "Cooking / Baking",
    "Fitness",
    "Study",
]


class FolderFilingSheet(ClaySheet):
    """Modal bottom sheet for searchable folder selection."""

    def __init__(
        self,
        *,
        current_folder: str | None = None,
        available_folders: list[str] | None = None,
        on_select_folder: Callable[[str | None], Any] | None = None,
        on_cancel: Callable[[], Any] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.selected_folder = current_folder
        self.all_folders = available_folders if available_folders is not None else list(DEFAULT_FOLDERS)
        self.on_select_folder = on_select_folder
        self.on_cancel = on_cancel
        self.theme_mode_val = theme_mode

        palette = get_palette(theme_mode)

        # Title
        self.title_text = ft.Text(
            "Move to folder",
            style=create_text_style(
                size=FONT_SIZE_TITLE_LARGE,
                weight=ft.FontWeight.BOLD,
                color=palette["ink"],
            ),
        )

        # Search field
        self.search_field = ft.TextField(
            hint_text="search folders…",
            text_size=FONT_SIZE_BODY,
            bgcolor=palette["background"],
            border_color=palette["line"],
            focused_border_color=palette["accent"],
            content_padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
            on_change=self._handle_search_change,
        )

        # Container for folder chips
        self.folders_wrap = ft.Row(
            controls=[],
            wrap=True,
            spacing=SPACING_8,
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

        button_row = ft.Row(
            controls=[
                self.cancel_button,
                ft.Container(expand=True),
                self.done_button,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self._rebuild_folder_chips()

        sheet_content = ft.Column(
            controls=[
                self.title_text,
                ft.Container(height=SPACING_8),
                self.search_field,
                ft.Container(height=SPACING_12),
                self.folders_wrap,
                ft.Container(height=SPACING_16),
                button_row,
            ],
            tight=True,
            spacing=0,
        )

        super().__init__(
            content=sheet_content,
            theme_mode=theme_mode,
        )

    def _rebuild_folder_chips(self, filter_query: str = "") -> None:
        """Construct selectable folder chips based on search query."""
        q = filter_query.lower().strip()
        filtered = [f for f in self.all_folders if not q or q in f.lower()]

        chips: list[ft.Control] = []

        # Option for Unfiled / Inbox
        is_unfiled_active = (self.selected_folder is None or self.selected_folder == "")
        chips.append(
            FolderChip(
                "Inbox (Unfiled)",
                prefix="",
                is_active=is_unfiled_active,
                on_click=lambda _: self._select_path(None),
                theme_mode=self.theme_mode_val,
            )
        )

        for folder_path in filtered:
            is_active = (folder_path == self.selected_folder)
            chips.append(
                FolderChip(
                    folder_path,
                    prefix="",
                    is_active=is_active,
                    on_click=lambda _, p=folder_path: self._select_path(p),
                    theme_mode=self.theme_mode_val,
                )
            )

        self.folders_wrap.controls = chips

    def _select_path(self, path: str | None) -> None:
        """Select a folder and refresh chip active states."""
        self.selected_folder = path
        query = (self.search_field.value or "").strip()
        self._rebuild_folder_chips(query)

    def _handle_search_change(self, e: Any) -> None:
        """Filter folder chips as user types."""
        query = (self.search_field.value or "").strip()
        self._rebuild_folder_chips(query)

    def done(self) -> None:
        """Confirm selection and dispatch callback."""
        if self.on_select_folder is not None:
            self.on_select_folder(self.selected_folder)

    def cancel(self) -> None:
        """Dismiss without applying changes."""
        if self.on_cancel is not None:
            self.on_cancel()

