"""Note Header and Breadcrumb Navigation for ClayBank Item Notes.

Provides top navigation controls including back navigation, folder breadcrumb with
'↩ move' shortcut, Edit/Done toggle button, and overflow PopupMenu with Move, Edit Tags,
Reprocess, and Delete actions.

Derived from Docs/UIUX.md §6 and Prototype v2 Screen 8.
"""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from app.shell.icons import IconName, get_icon
from app.shell.theme import get_palette
from app.shell.tokens import (
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_LABEL,
    MIN_TOUCH_TARGET,
    PILL_RADIUS,
    SPACING_4,
    SPACING_8,
    SPACING_12,
    create_text_style,
)


class NoteHeader(ft.Container):
    """Top navigation bar for an Item Note."""

    def __init__(
        self,
        *,
        folder_path: str | None = None,
        is_editing: bool = False,
        on_back: Callable[[], Any] | None = None,
        on_toggle_edit: Callable[[bool], Any] | None = None,
        on_move: Callable[[], Any] | None = None,
        on_menu_action: Callable[[str], Any] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.folder_path_val = folder_path
        self.is_editing_val = is_editing
        self.on_back = on_back
        self.on_toggle_edit = on_toggle_edit
        self.on_move = on_move
        self.on_menu_action = on_menu_action
        self.theme_mode_val = theme_mode

        palette = get_palette(theme_mode)

        # Back button (44px target)
        self.back_button = ft.Container(
            content=get_icon(IconName.BACK, size=20.0, color=palette["ink"]),
            width=MIN_TOUCH_TARGET,
            height=MIN_TOUCH_TARGET,
            alignment=ft.Alignment(0, 0),
            border_radius=ft.BorderRadius.all(PILL_RADIUS),
            on_click=lambda _: self.trigger_back(),
            tooltip="Back",
        )

        # Breadcrumb elements
        self.breadcrumb_text = ft.Text(
            spans=self._build_breadcrumb_spans(folder_path, palette),
            no_wrap=True,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        # '↩ move' affordance button
        self.move_affordance = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(
                        "↩ move",
                        style=create_text_style(
                            size=FONT_SIZE_LABEL,
                            color=palette["accent_ink"],
                            weight=ft.FontWeight.W_500,
                        ),
                    ),
                ],
                tight=True,
                spacing=SPACING_4,
            ),
            bgcolor=palette["accent_bg"],
            padding=ft.Padding.symmetric(horizontal=SPACING_8, vertical=SPACING_4),
            border_radius=ft.BorderRadius.all(PILL_RADIUS),
            on_click=lambda _: self.trigger_move(),
            tooltip="Move to folder",
        )

        self.breadcrumb_container = ft.Row(
            controls=[
                self.breadcrumb_text,
                self.move_affordance,
            ],
            spacing=SPACING_8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        )

        # Edit / Done mode toggle button
        self.edit_button_text = ft.Text(
            "Done" if is_editing else "Edit",
            style=create_text_style(
                size=FONT_SIZE_LABEL,
                weight=ft.FontWeight.BOLD,
                color=palette["ink"],
            ),
        )
        self.edit_button = ft.Container(
            content=self.edit_button_text,
            padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
            bgcolor=palette["chip"],
            border_radius=ft.BorderRadius.all(PILL_RADIUS),
            height=MIN_TOUCH_TARGET,
            alignment=ft.Alignment(0, 0),
            on_click=lambda _: self.toggle_edit(),
            tooltip="Toggle Edit / Preview",
        )

        # Overflow menu items
        self.overflow_menu = ft.PopupMenuButton(
            content=ft.Container(
                content=get_icon(IconName.OVERFLOW, size=20.0, color=palette["ink"]),
                width=MIN_TOUCH_TARGET,
                height=MIN_TOUCH_TARGET,
                alignment=ft.Alignment(0, 0),
                border_radius=ft.BorderRadius.all(PILL_RADIUS),
            ),
            items=[
                ft.PopupMenuItem(
                    content=ft.Row(
                        controls=[
                            get_icon(IconName.FOLDER, size=18.0, color=palette["ink"]),
                            ft.Text("Move to folder…"),
                        ],
                        spacing=SPACING_8,
                    ),
                    on_click=lambda _: self.trigger_menu_action("move"),
                ),
                ft.PopupMenuItem(
                    content=ft.Row(
                        controls=[
                            get_icon(IconName.TAGS, size=18.0, color=palette["ink"]),
                            ft.Text("Edit tags…"),
                        ],
                        spacing=SPACING_8,
                    ),
                    on_click=lambda _: self.trigger_menu_action("tags"),
                ),
                ft.PopupMenuItem(
                    content=ft.Row(
                        controls=[
                            get_icon("refresh", size=18.0, color=palette["ink"]),
                            ft.Text("Reprocess (metadata & transcript only)"),
                        ],
                        spacing=SPACING_8,
                    ),
                    on_click=lambda _: self.trigger_menu_action("reprocess"),
                ),
                ft.PopupMenuItem(
                    content=ft.Row(
                        controls=[
                            get_icon("delete", size=18.0, color=palette["accent_ink"]),
                            ft.Text(
                                "Delete…",
                                style=create_text_style(
                                    color=palette["accent_ink"],
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ),
                        ],
                        spacing=SPACING_8,
                    ),
                    on_click=lambda _: self.trigger_menu_action("delete"),
                ),
            ],
            tooltip="More options",
        )

        layout_row = ft.Row(
            controls=[
                self.back_button,
                self.breadcrumb_container,
                self.edit_button,
                self.overflow_menu,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=SPACING_8,
        )

        super().__init__(
            content=layout_row,
            padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
            bgcolor=palette["background"],
            border=ft.Border(
                bottom=ft.BorderSide(1.0, palette["line"]),
            ),
        )

    def _build_breadcrumb_spans(
        self, folder_path: str | None, palette: dict[str, str]
    ) -> list[ft.TextSpan]:
        """Construct styled text spans for breadcrumb path."""
        muted_style = create_text_style(
            size=FONT_SIZE_BODY,
            color=palette["muted"],
        )
        bold_style = create_text_style(
            size=FONT_SIZE_BODY,
            color=palette["ink"],
            weight=ft.FontWeight.BOLD,
        )

        if not folder_path or not folder_path.strip():
            return [
                ft.TextSpan("Inbox", style=bold_style),
            ]

        parts = [p.strip() for p in folder_path.split("/") if p.strip()]
        if not parts:
            return [ft.TextSpan("Inbox", style=bold_style)]

        spans: list[ft.TextSpan] = [
            ft.TextSpan("Folders / ", style=muted_style),
        ]
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                spans.append(ft.TextSpan(part, style=bold_style))
            else:
                spans.append(ft.TextSpan(f"{part} / ", style=muted_style))

        return spans

    def set_folder_path(self, folder_path: str | None) -> None:
        """Update breadcrumb path dynamically."""
        self.folder_path_val = folder_path
        palette = get_palette(self.theme_mode_val)
        self.breadcrumb_text.spans = self._build_breadcrumb_spans(folder_path, palette)

    def set_editing(self, is_editing: bool) -> None:
        """Update Edit/Done button text according to active mode."""
        self.is_editing_val = is_editing
        self.edit_button_text.value = "Done" if is_editing else "Edit"

    def toggle_edit(self) -> None:
        """Toggle editing state and invoke callback."""
        new_state = not self.is_editing_val
        self.set_editing(new_state)
        if self.on_toggle_edit is not None:
            self.on_toggle_edit(new_state)

    def trigger_back(self) -> None:
        """Handle back button tap."""
        if self.on_back is not None:
            self.on_back()

    def trigger_move(self) -> None:
        """Handle move affordance tap."""
        if self.on_move is not None:
            self.on_move()

    def trigger_menu_action(self, action: str) -> None:
        """Dispatch overflow menu action."""
        if self.on_menu_action is not None:
            self.on_menu_action(action)
