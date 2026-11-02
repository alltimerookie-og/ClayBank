"""Folders Grid View for ClayBank (Main screen for Tab 1).

Derived from Docs/Design.md §7.4, Docs/UIUX.md §7, and Prototype v2 Screen 10.
Features:
- Header with Library breadcrumb and "+ New folder" button.
- Sorting row with interactive chips: Recent, A to Z, Most saved.
- 2-column grid of FolderCard items with deterministic collages.
- Empty state with prompt when no folders exist.
- Pure client-side sorting and immediate responsiveness.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_H1,
    FONT_SIZE_LABEL,
    FONT_SIZE_MICRO,
    FONT_SIZE_MUTED,
    MIN_TOUCH_TARGET,
    PILL_RADIUS,
    SPACING_8,
    SPACING_12,
    SPACING_16,
    SPACING_24,
    create_text_style,
)
from app.views.folders.folder_card import FolderCard

SORT_RECENT = "recent"
SORT_ALPHA = "alpha"
SORT_SAVES = "saves"


def sort_folders(
    folders: Sequence[dict[str, Any]],
    sort_by: str = SORT_RECENT,
) -> list[dict[str, Any]]:
    """Sort a list of folder dictionaries according to the selected strategy."""
    items = list(folders)
    if sort_by == SORT_ALPHA:
        return sorted(items, key=lambda f: str(f.get("name") or "").lower())
    elif sort_by == SORT_SAVES:
        return sorted(items, key=lambda f: int(f.get("save_count") or 0), reverse=True)
    else:  # SORT_RECENT
        return sorted(
            items,
            key=lambda f: str(f.get("updated_at") or f.get("created_at") or ""),
            reverse=True,
        )


class FoldersGridView(ft.Container):
    """Main Folders tab view presenting user folders in a 2-column grid."""

    def __init__(
        self,
        *,
        folders: Sequence[dict[str, Any]] | None = None,
        on_select_folder: Callable[[dict[str, Any]], None] | None = None,
        on_new_folder: Callable[[], None] | None = None,
        on_folder_long_press: Callable[[dict[str, Any]], None] | None = None,
        on_refresh: Callable[[], None] | None = None,
        is_loading: bool = False,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self._raw_folders = list(folders or [])
        self.active_sort = SORT_RECENT
        self.on_select_folder = on_select_folder
        self.on_new_folder = on_new_folder
        self.on_folder_long_press = on_folder_long_press
        self.on_refresh = on_refresh
        self.theme_mode_val = theme_mode
        self._is_loading = is_loading

        palette = get_palette(theme_mode)

        # 1. Header with Library breadcrumb and + New folder button
        self.breadcrumb_text = ft.Text(
            "Library",
            size=FONT_SIZE_LABEL,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
            weight=ft.FontWeight.W_500,
        )
        self.header_title = ft.Text(
            "Folders",
            size=FONT_SIZE_H1,
            weight=ft.FontWeight.BOLD,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
        )

        header_left = ft.Column(
            controls=[self.breadcrumb_text, self.header_title],
            spacing=2.0,
            tight=True,
        )

        self.new_button = ft.FilledButton(
            "+ New folder",
            on_click=lambda _: self._handle_new_folder(),
            style=ft.ButtonStyle(
                bgcolor=palette["accent_bg"],
                color=palette["accent_ink"],
            ),
            height=36.0,
        )

        self.refresh_button = ft.IconButton(
            icon=ft.Icons.REFRESH_ROUNDED,
            icon_color=palette["muted"],
            icon_size=20.0,
            tooltip="Refresh Folders",
            on_click=lambda _: self._handle_refresh(),
        )

        header_row = ft.Row(
            controls=[
                header_left,
                ft.Row(
                    controls=[self.refresh_button, self.new_button],
                    spacing=SPACING_8,
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # 2. Loading Bar
        self.loading_bar = ft.ProgressBar(
            color=palette["accent"],
            bgcolor=palette["chip"],
            visible=is_loading,
        )

        # 3. Sorting Chips
        self.sort_row = ft.Row(spacing=SPACING_8)
        self._rebuild_sort_chips()

        # 4. Grid Container
        self.grid_column = ft.Column(spacing=SPACING_12)
        self._rebuild_grid()

        # Overall scrollable column
        main_col = ft.Column(
            controls=[
                header_row,
                self.loading_bar,
                self.sort_row,
                self.grid_column,
            ],
            spacing=SPACING_16,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        super().__init__(
            content=main_col,
            padding=ft.Padding.symmetric(horizontal=SPACING_16, vertical=SPACING_12),
            bgcolor=palette["background"],
            expand=True,
            theme_mode=theme_mode if isinstance(theme_mode, ft.ThemeMode) else None,
        )

    def _handle_new_folder(self) -> None:
        if self.on_new_folder:
            self.on_new_folder()

    def _handle_refresh(self) -> None:
        if self.on_refresh:
            self.on_refresh()

    def set_folders(self, folders: Sequence[dict[str, Any]]) -> None:
        """Update folder collection and re-render grid."""
        self._raw_folders = list(folders)
        self._rebuild_grid()
        try:
            self.update()
        except Exception:
            pass

    def set_loading(self, is_loading: bool) -> None:
        """Toggle loading progress bar."""
        self._is_loading = is_loading
        self.loading_bar.visible = is_loading
        try:
            self.update()
        except Exception:
            pass

    def _set_sort(self, sort_type: str) -> None:
        """Change active sort order and rebuild view."""
        self.active_sort = sort_type
        self._rebuild_sort_chips()
        self._rebuild_grid()
        try:
            self.update()
        except Exception:
            pass

    def _rebuild_sort_chips(self) -> None:
        palette = get_palette(self.theme_mode_val)
        chip_specs = [
            (SORT_RECENT, "Recent"),
            (SORT_ALPHA, "A to Z"),
            (SORT_SAVES, "Most saved"),
        ]

        chips: list[ft.Control] = []
        for s_type, label in chip_specs:
            is_active = self.active_sort == s_type
            bg = palette["accent_bg"] if is_active else palette["chip"]
            fg = palette["accent_ink"] if is_active else palette["chip_ink"]
            border = (
                ft.Border.all(1.0, palette["accent"])
                if is_active
                else ft.Border.all(1.0, palette["line"])
            )

            btn = ft.Container(
                content=ft.Text(
                    label,
                    size=FONT_SIZE_MICRO,
                    weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.W_500,
                    color=fg,
                    font_family=FONT_FAMILY_UI,
                ),
                bgcolor=bg,
                border=border,
                border_radius=ft.BorderRadius.all(PILL_RADIUS),
                padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
                on_click=lambda e, st=s_type: self._set_sort(st),
                alignment=ft.Alignment(0, 0),
            )
            chips.append(btn)

        self.sort_row.controls = chips

    def _rebuild_grid(self) -> None:
        palette = get_palette(self.theme_mode_val)
        sorted_items = sort_folders(self._raw_folders, self.active_sort)

        if not sorted_items:
            empty_icon = ft.Icon(
                ft.Icons.FOLDER_OPEN_OUTLINED,
                size=48.0,
                color=palette["muted"],
            )
            empty_title = ft.Text(
                "No folders yet",
                style=create_text_style(
                    size=FONT_SIZE_BODY,
                    weight=ft.FontWeight.W_600,
                    color=palette["ink"],
                ),
            )
            empty_desc = ft.Text(
                "Folders appear when you have a project to put them in. Folders are for projects, not topics — there is no 'Unsorted' folder.",
                style=create_text_style(
                    size=FONT_SIZE_MUTED,
                    color=palette["muted"],
                ),
                text_align=ft.TextAlign.CENTER,
            )
            create_btn = ft.FilledButton(
                "+ Create folder",
                on_click=lambda _: self._handle_new_folder(),
                style=ft.ButtonStyle(
                    bgcolor=palette["accent"],
                    color=palette["accent_fg"],
                ),
                height=MIN_TOUCH_TARGET,
            )

            empty_view = ft.Container(
                content=ft.Column(
                    controls=[empty_icon, empty_title, empty_desc, create_btn],
                    spacing=SPACING_12,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True,
                ),
                padding=ft.Padding.symmetric(vertical=SPACING_24, horizontal=SPACING_16),
                alignment=ft.Alignment(0, 0),
            )
            self.grid_column.controls = [empty_view]
            return

        # Build 2-column paired rows
        grid_rows: list[ft.Control] = []
        for i in range(0, len(sorted_items), 2):
            first_folder = sorted_items[i]
            card_first = FolderCard(
                first_folder,
                on_click=self.on_select_folder,
                on_long_press=self.on_folder_long_press,
                theme_mode=self.theme_mode_val,
            )
            row_items: list[ft.Control] = [ft.Container(content=card_first, expand=1)]

            if i + 1 < len(sorted_items):
                second_folder = sorted_items[i + 1]
                card_second = FolderCard(
                    second_folder,
                    on_click=self.on_select_folder,
                    on_long_press=self.on_folder_long_press,
                    theme_mode=self.theme_mode_val,
                )
                row_items.append(ft.Container(content=card_second, expand=1))
            else:
                # Add an empty container for balanced 2-column alignment
                row_items.append(ft.Container(expand=1))

            grid_rows.append(
                ft.Row(
                    controls=row_items,
                    spacing=SPACING_12,
                    alignment=ft.MainAxisAlignment.START,
                )
            )

        self.grid_column.controls = grid_rows

