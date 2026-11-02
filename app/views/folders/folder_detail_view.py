"""Folder Detail View for ClayBank (Screen 11).

Derived from Docs/Design.md §7.4, Docs/UIUX.md §7-8, and Prototype v2 Screen 11.
Implements the core UX contract:
- Two Rows, Two Verbs:
  1. FOLDERS row: Outlined FolderChips with chevron for drilling down (Navigate).
  2. TAGS row: Filled TagChips for filtering the stream in place (Filter in place).
- Saves stream filtered in place without network round-trips.
- Breadcrumbs, folder title, save count, and overflow actions.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence
from urllib.parse import urlparse
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_H1,
    FONT_SIZE_LABEL,
    FONT_SIZE_MICRO,
    FONT_SIZE_MUTED,
    FONT_SIZE_TITLE,
    MIN_TOUCH_TARGET,
    PILL_RADIUS,
    SPACING_4,
    SPACING_6,
    SPACING_8,
    SPACING_12,
    SPACING_16,
    SPACING_24,
    create_text_style,
)
from app.ui.card import ClayCard
from app.ui.chips import FolderChip, PlatformChip, TagChip
from app.views.folders.folder_dialogs import MAX_FOLDER_DEPTH


class FolderSaveCard(ClayCard):
    """Card representing a save within a folder, with title, platform, and tags."""

    def __init__(
        self,
        save_item: dict[str, Any],
        *,
        on_click: Callable[[dict[str, Any]], None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.save_item = dict(save_item)
        self.save_id = str(save_item.get("id") or "")
        self.on_click_callback = on_click
        palette = get_palette(theme_mode)

        title_val = save_item.get("title") or save_item.get("user_context")
        if not title_val:
            url = save_item.get("url", "")
            try:
                parsed = urlparse(url)
                title_val = parsed.netloc.replace("www.", "") if parsed.netloc else url
            except Exception:
                title_val = url or "Save"

        self.title_text = ft.Text(
            value=str(title_val),
            size=FONT_SIZE_TITLE,
            weight=ft.FontWeight.W_600,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        platform = save_item.get("platform") or save_item.get("source_app") or "web"
        meta_controls: list[ft.Control] = [
            PlatformChip(platform=platform, theme_mode=theme_mode),
        ]

        # Add tag previews if present
        raw_tags = save_item.get("tags") or []
        for tag in raw_tags[:3]:
            meta_controls.append(
                ft.Text(
                    f"#{tag.lstrip('#')}",
                    size=FONT_SIZE_MICRO,
                    color=palette["muted"],
                    font_family=FONT_FAMILY_UI,
                )
            )

        meta_row = ft.Row(
            controls=meta_controls,
            spacing=SPACING_8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True,
        )

        col = ft.Column(
            controls=[self.title_text, meta_row],
            spacing=SPACING_6,
            tight=True,
        )

        super().__init__(
            content=col,
            padding=SPACING_12,
            theme_mode=theme_mode,
            on_click=lambda _: self._handle_click(),
        )

    def _handle_click(self) -> None:
        if self.on_click_callback:
            self.on_click_callback(self.save_item)


class FolderDetailView(ft.Container):
    """Detail drill-down view for an individual folder."""

    def __init__(
        self,
        folder_data: dict[str, Any],
        *,
        subfolders: Sequence[dict[str, Any]] | None = None,
        saves: Sequence[dict[str, Any]] | None = None,
        tags: Sequence[str] | None = None,
        folder_depth: int = 1,
        breadcrumb_trail: Sequence[tuple[str, str]] | None = None,
        on_back: Callable[[], None] | None = None,
        on_select_subfolder: Callable[[dict[str, Any]], None] | None = None,
        on_select_save: Callable[[dict[str, Any]], None] | None = None,
        on_rename_folder: Callable[[dict[str, Any]], None] | None = None,
        on_add_subfolder: Callable[[dict[str, Any]], None] | None = None,
        on_delete_folder: Callable[[dict[str, Any]], None] | None = None,
        on_ask_folder: Callable[[str, str], None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.folder_data = dict(folder_data)
        self.folder_id = str(folder_data.get("id") or "")
        self.folder_name = str(folder_data.get("name") or "Folder")
        self.folder_depth = folder_depth
        self._subfolders = list(subfolders or [])
        self._raw_saves = list(saves or [])
        self.selected_tag: str | None = None

        self.on_back = on_back
        self.on_select_subfolder = on_select_subfolder
        self.on_select_save = on_select_save
        self.on_rename_folder = on_rename_folder
        self.on_add_subfolder = on_add_subfolder
        self.on_delete_folder = on_delete_folder
        self.on_ask_folder = on_ask_folder
        self.theme_mode_val = theme_mode

        # Gather distinct tags
        if tags is not None:
            self.all_tags = list(tags)
        else:
            tag_set: set[str] = set()
            for s in self._raw_saves:
                for t in s.get("tags") or []:
                    tag_set.add(t.lstrip("#"))
            self.all_tags = sorted(tag_set)

        palette = get_palette(theme_mode)

        # 1. Back button & Breadcrumb bar
        self.back_button = ft.TextButton(
            "‹ Folders",
            on_click=lambda _: self._handle_back(),
            style=ft.ButtonStyle(color=palette["accent_ink"]),
        )

        breadcrumb_str = "Folders / " + self.folder_name
        if breadcrumb_trail:
            names = [name for _, name in breadcrumb_trail]
            breadcrumb_str = " / ".join(["Folders"] + names)

        self.breadcrumb_text = ft.Text(
            breadcrumb_str,
            size=FONT_SIZE_LABEL,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
        )

        nav_row = ft.Row(
            controls=[self.back_button, self.breadcrumb_text],
            spacing=SPACING_8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # 2. Folder title and save count
        self.title_text = ft.Text(
            self.folder_name,
            size=FONT_SIZE_H1,
            weight=ft.FontWeight.BOLD,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
        )

        save_count = len(self._raw_saves)
        count_label = f"{save_count} saves" if save_count > 0 else ""
        self.count_text = ft.Text(
            count_label,
            size=FONT_SIZE_MUTED,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
            visible=bool(count_label),
        )

        header_info = ft.Column(
            controls=[self.title_text, self.count_text],
            spacing=2.0,
            tight=True,
        )

        # Overflow menu items
        menu_items: list[ft.PopupMenuItem] = [
            ft.PopupMenuItem(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=18.0, color=palette["ink"]),
                        ft.Text("Ask folder", color=palette["ink"]),
                    ],
                    spacing=SPACING_8,
                ),
                on_click=lambda _: self._handle_ask_folder(),
            ),
            ft.PopupMenuItem(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.EDIT_ROUNDED, size=18.0, color=palette["ink"]),
                        ft.Text("Rename", color=palette["ink"]),
                    ],
                    spacing=SPACING_8,
                ),
                on_click=lambda _: self._handle_rename(),
            ),
        ]

        if self.folder_depth < MAX_FOLDER_DEPTH:
            menu_items.append(
                ft.PopupMenuItem(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CREATE_NEW_FOLDER_ROUNDED, size=18.0, color=palette["ink"]),
                            ft.Text("Add subfolder", color=palette["ink"]),
                        ],
                        spacing=SPACING_8,
                    ),
                    on_click=lambda _: self._handle_add_subfolder(),
                )
            )

        menu_items.append(
            ft.PopupMenuItem(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED, size=18.0, color=palette["accent"]),
                        ft.Text("Delete folder", color=palette["accent"]),
                    ],
                    spacing=SPACING_8,
                ),
                on_click=lambda _: self._handle_delete(),
            )
        )

        self.overflow_menu = ft.PopupMenuButton(
            icon=ft.Icons.MORE_HORIZ_ROUNDED,
            icon_color=palette["ink"],
            items=menu_items,
        )

        title_row = ft.Row(
            controls=[header_info, self.overflow_menu],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # 3. Two Rows, Two Verbs
        # Row 1: FOLDERS (Verb: Navigate)
        self.folders_section = ft.Column(spacing=SPACING_6, tight=True)
        self._rebuild_subfolders_row()

        # Row 2: TAGS (Verb: Filter in place)
        self.tags_section = ft.Column(spacing=SPACING_6, tight=True)
        self._rebuild_tags_row()

        # 4. Saves Stream Column
        self.saves_column = ft.Column(spacing=SPACING_8)
        self._rebuild_saves_list()

        main_col = ft.Column(
            controls=[
                nav_row,
                title_row,
                self.folders_section,
                self.tags_section,
                self.saves_column,
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

    def _handle_back(self) -> None:
        if self.on_back:
            self.on_back()

    def _handle_ask_folder(self) -> None:
        if self.on_ask_folder:
            self.on_ask_folder(self.folder_id, self.folder_name)

    def _handle_rename(self) -> None:
        if self.on_rename_folder:
            self.on_rename_folder(self.folder_data)

    def _handle_add_subfolder(self) -> None:
        if self.on_add_subfolder:
            self.on_add_subfolder(self.folder_data)

    def _handle_delete(self) -> None:
        if self.on_delete_folder:
            self.on_delete_folder(self.folder_data)

    def _rebuild_subfolders_row(self) -> None:
        palette = get_palette(self.theme_mode_val)
        chips: list[ft.Control] = []

        for sf in self._subfolders:
            sf_name = str(sf.get("name") or "")
            raw_c = sf.get("save_count")
            sf_count = int(raw_c) if raw_c is not None else 0
            chip = FolderChip(
                path=sf_name,
                count=sf_count if sf_count > 0 else None,
                chevron=True,
                on_click=lambda e, s=sf: self._select_subfolder(s),
                theme_mode=self.theme_mode_val,
            )
            chips.append(chip)

        if self.folder_depth < MAX_FOLDER_DEPTH:
            add_sub_btn = ft.Container(
                content=ft.Text(
                    "+ subfolder",
                    size=FONT_SIZE_MICRO,
                    color=palette["muted"],
                    font_family=FONT_FAMILY_UI,
                ),
                border=ft.Border.all(1.0, palette["line"]),
                border_radius=ft.BorderRadius.all(PILL_RADIUS),
                padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
                on_click=lambda _: self._handle_add_subfolder(),
            )
            chips.append(add_sub_btn)

        if chips:
            label = ft.Text(
                "FOLDERS",
                size=FONT_SIZE_LABEL,
                weight=ft.FontWeight.BOLD,
                color=palette["muted"],
                font_family=FONT_FAMILY_UI,
            )
            chip_row = ft.Row(
                controls=chips,
                spacing=SPACING_8,
                wrap=True,
            )
            self.folders_section.controls = [label, chip_row]
            self.folders_section.visible = True
        else:
            self.folders_section.visible = False

    def _select_subfolder(self, subfolder: dict[str, Any]) -> None:
        if self.on_select_subfolder:
            self.on_select_subfolder(subfolder)

    def _rebuild_tags_row(self) -> None:
        palette = get_palette(self.theme_mode_val)
        if not self.all_tags:
            self.tags_section.visible = False
            return

        chips: list[ft.Control] = []

        # "All" filter chip
        all_selected = self.selected_tag is None
        all_chip = ft.Container(
            content=ft.Text(
                "All",
                size=FONT_SIZE_MICRO,
                weight=ft.FontWeight.W_600 if all_selected else ft.FontWeight.W_500,
                color=palette["accent_ink"] if all_selected else palette["chip_ink"],
                font_family=FONT_FAMILY_UI,
            ),
            bgcolor=palette["accent_bg"] if all_selected else palette["chip"],
            border=ft.Border.all(1.0, palette["accent"]) if all_selected else None,
            border_radius=ft.BorderRadius.all(PILL_RADIUS),
            padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
            on_click=lambda _: self._set_tag_filter(None),
        )
        chips.append(all_chip)

        for tag in self.all_tags:
            clean_tag = tag.lstrip("#")
            is_sel = self.selected_tag == clean_tag
            chip = TagChip(
                name=clean_tag,
                selected=is_sel,
                on_click=lambda e, t=clean_tag: self._set_tag_filter(t),
                theme_mode=self.theme_mode_val,
            )
            chips.append(chip)

        label = ft.Text(
            "TAGS",
            size=FONT_SIZE_LABEL,
            weight=ft.FontWeight.BOLD,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
        )
        tags_row = ft.Row(
            controls=chips,
            spacing=SPACING_8,
            wrap=True,
        )
        self.tags_section.controls = [label, tags_row]
        self.tags_section.visible = True

    def _set_tag_filter(self, tag: str | None) -> None:
        """Filter saves stream in-place without page reload or backend fetch."""
        if self.selected_tag == tag:
            self.selected_tag = None
        else:
            self.selected_tag = tag
        self._rebuild_tags_row()
        self._rebuild_saves_list()
        try:
            self.update()
        except Exception:
            pass

    def _rebuild_saves_list(self) -> None:
        palette = get_palette(self.theme_mode_val)

        # Filter saves by selected tag if set
        filtered: list[dict[str, Any]] = []
        for s in self._raw_saves:
            if self.selected_tag is None:
                filtered.append(s)
            else:
                s_tags = [t.lstrip("#").lower() for t in s.get("tags") or []]
                if self.selected_tag.lower() in s_tags:
                    filtered.append(s)

        if not filtered:
            if self.selected_tag:
                msg = f"No saves in this folder match #{self.selected_tag}."
            else:
                msg = "No saves in this folder yet. Move saves here from your Inbox."

            empty_text = ft.Text(
                msg,
                style=create_text_style(
                    size=FONT_SIZE_BODY,
                    color=palette["muted"],
                ),
                text_align=ft.TextAlign.CENTER,
            )
            self.saves_column.controls = [
                ft.Container(
                    content=empty_text,
                    padding=ft.Padding.symmetric(vertical=SPACING_24),
                    alignment=ft.Alignment(0, 0),
                )
            ]
            return

        save_cards: list[ft.Control] = []
        for save_item in filtered:
            card = FolderSaveCard(
                save_item,
                on_click=self.on_select_save,
                theme_mode=self.theme_mode_val,
            )
            save_cards.append(card)

        self.saves_column.controls = save_cards

    def set_data(
        self,
        folder_data: dict[str, Any],
        subfolders: Sequence[dict[str, Any]] | None = None,
        saves: Sequence[dict[str, Any]] | None = None,
    ) -> None:
        """Update folder view state and rebuild components."""
        self.folder_data = dict(folder_data)
        self.folder_name = str(folder_data.get("name") or "Folder")
        self.title_text.value = self.folder_name
        if subfolders is not None:
            self._subfolders = list(subfolders)
        if saves is not None:
            self._raw_saves = list(saves)
            save_count = len(self._raw_saves)
            self.count_text.value = f"{save_count} saves" if save_count > 0 else ""
            self.count_text.visible = bool(self.count_text.value)

            # Re-collect tags
            tag_set: set[str] = set()
            for s in self._raw_saves:
                for t in s.get("tags") or []:
                    tag_set.add(t.lstrip("#"))
            self.all_tags = sorted(tag_set)

        self._rebuild_subfolders_row()
        self._rebuild_tags_row()
        self._rebuild_saves_list()
        try:
            self.update()
        except Exception:
            pass
