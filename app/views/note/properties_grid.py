"""Properties Grid for ClayBank Item Notes.

Renders frontmatter facts in a clean two-column grid (96px label column):
- Read-only facts: source, channel, video_url, duration, published, saved.
- Live interactive controls: folder (triggers filing sheet) and tags (triggers tag editor).

Derived from Docs/UIUX.md §6, Docs/adr/0005-markdown-as-source-of-truth.md,
and Prototype v2 Screen 8.
"""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    FONT_SIZE_LABEL,
    FONT_SIZE_MICRO,
    PILL_RADIUS,
    SPACING_4,
    SPACING_8,
    SPACING_12,
    create_text_style,
)
from app.ui.chips import FolderChip, TagChip
from app.views.note.note_engine import format_duration


class PropertiesGrid(ft.Container):
    """Two-column Properties Grid displaying fact-only frontmatter metadata."""

    def __init__(
        self,
        *,
        frontmatter: dict[str, Any] | None = None,
        on_edit_folder: Callable[[], Any] | None = None,
        on_edit_tags: Callable[[], Any] | None = None,
        on_open_url: Callable[[str], Any] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.frontmatter_val = frontmatter or {}
        self.on_edit_folder = on_edit_folder
        self.on_edit_tags = on_edit_tags
        self.on_open_url = on_open_url
        self.theme_mode_val = theme_mode

        self.rows_column = ft.Column(spacing=SPACING_4)
        self.rebuild_grid()

        palette = get_palette(theme_mode)

        # Header caption row: "Properties" + "folder & tags are editable ✎"
        caption_row = ft.Row(
            controls=[
                ft.Text(
                    "Properties",
                    style=create_text_style(
                        size=FONT_SIZE_LABEL,
                        color=palette["muted"],
                        weight=ft.FontWeight.W_500,
                    ),
                ),
                ft.Text(
                    "folder & tags are editable ✎",
                    style=create_text_style(
                        size=FONT_SIZE_MICRO,
                        color=palette["muted"],
                    ),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        grid_content = ft.Column(
            controls=[
                caption_row,
                ft.Container(height=SPACING_4),
                self.rows_column,
            ],
            spacing=0,
        )

        super().__init__(
            content=grid_content,
            padding=ft.Padding.only(bottom=SPACING_12),
            border=ft.Border(bottom=ft.BorderSide(1.0, palette["line"])),
        )

    def rebuild_grid(self) -> None:
        """Construct key-value rows from current frontmatter dictionary."""
        palette = get_palette(self.theme_mode_val)
        rows: list[ft.Control] = []

        # 1. source (read-only)
        source = self.frontmatter_val.get("source")
        if source:
            rows.append(self._build_row("source", ft.Text(str(source), size=FONT_SIZE_LABEL, color=palette["ink"])))

        # 2. channel (read-only)
        channel = self.frontmatter_val.get("channel")
        if channel:
            rows.append(self._build_row("channel", ft.Text(str(channel), size=FONT_SIZE_LABEL, color=palette["ink"])))

        # 3. video_url (read-only link)
        video_url = self.frontmatter_val.get("video_url")
        if video_url:
            url_str = str(video_url)
            link_text = ft.Text(
                url_str,
                size=FONT_SIZE_LABEL,
                color=palette["accent"],
                no_wrap=True,
                overflow=ft.TextOverflow.ELLIPSIS,
            )
            link_row = ft.Container(
                content=link_text,
                on_click=lambda _: self._handle_url_click(url_str),
                tooltip=url_str,
            )
            rows.append(self._build_row("video_url", link_row))

        # 4. duration (read-only)
        duration = self.frontmatter_val.get("duration")
        if duration is not None:
            dur_str = format_duration(duration)
            if dur_str:
                rows.append(self._build_row("duration", ft.Text(dur_str, size=FONT_SIZE_LABEL, color=palette["ink"])))

        # 5. published (read-only)
        published = self.frontmatter_val.get("published")
        if published:
            rows.append(self._build_row("published", ft.Text(str(published), size=FONT_SIZE_LABEL, color=palette["ink"])))

        # 6. saved (read-only)
        saved = self.frontmatter_val.get("saved")
        if saved:
            rows.append(self._build_row("saved", ft.Text(str(saved), size=FONT_SIZE_LABEL, color=palette["ink"])))

        # 7. folder (live control)
        folder = self.frontmatter_val.get("folder")
        folder_display = str(folder) if folder else "(Unfiled)"
        folder_control = ft.Container(
            content=ft.Row(
                controls=[
                    FolderChip(
                        folder_display,
                        prefix="",
                        on_click=lambda _: self._handle_edit_folder(),
                        theme_mode=self.theme_mode_val,
                    ),
                    ft.Text(
                        "✎",
                        size=FONT_SIZE_LABEL,
                        color=palette["muted"],
                    ),
                ],
                tight=True,
                spacing=SPACING_4,
            ),
            on_click=lambda _: self._handle_edit_folder(),
            tooltip="Click to change folder",
        )
        rows.append(self._build_row("folder", folder_control))

        # 8. tags (live control)
        raw_tags = self.frontmatter_val.get("tags") or []
        tag_list = raw_tags if isinstance(raw_tags, list) else [str(raw_tags)]

        tag_controls: list[ft.Control] = [
            TagChip(
                t,
                selected=False,
                on_click=lambda _, t_val=t: self._handle_edit_tags(),
                theme_mode=self.theme_mode_val,
            )
            for t in tag_list
            if str(t).strip()
        ]
        if not tag_controls:
            tag_controls.append(
                ft.Text(
                    "(None)",
                    size=FONT_SIZE_LABEL,
                    color=palette["muted"],
                )
            )

        tag_controls.append(
            ft.Text(
                "✎",
                size=FONT_SIZE_LABEL,
                color=palette["muted"],
            )
        )

        tags_container = ft.Container(
            content=ft.Row(
                controls=tag_controls,
                wrap=True,
                spacing=SPACING_4,
            ),
            on_click=lambda _: self._handle_edit_tags(),
            tooltip="Click to edit tags",
        )
        rows.append(self._build_row("tags", tags_container))

        self.rows_column.controls = rows

    def _build_row(self, label: str, value_control: ft.Control) -> ft.Row:
        """Build standard two-column row with 96px fixed label width."""
        palette = get_palette(self.theme_mode_val)
        label_text = ft.Container(
            content=ft.Text(
                label,
                size=FONT_SIZE_LABEL,
                color=palette["muted"],
            ),
            width=96.0,
            alignment=ft.Alignment(-1, 0),
        )

        value_wrapper = ft.Container(
            content=value_control,
            expand=True,
            alignment=ft.Alignment(-1, 0),
        )

        return ft.Row(
            controls=[label_text, value_wrapper],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=SPACING_8,
        )

    def set_frontmatter(self, frontmatter: dict[str, Any]) -> None:
        """Update frontmatter and rebuild the properties display."""
        self.frontmatter_val = frontmatter or {}
        self.rebuild_grid()

    def _handle_edit_folder(self) -> None:
        """Dispatch folder edit callback."""
        if self.on_edit_folder is not None:
            self.on_edit_folder()

    def _handle_edit_tags(self) -> None:
        """Dispatch tags edit callback."""
        if self.on_edit_tags is not None:
            self.on_edit_tags()

    def _handle_url_click(self, url: str) -> None:
        """Dispatch video URL click callback."""
        if self.on_open_url is not None:
            self.on_open_url(url)
