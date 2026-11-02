"""Markdown Note Renderer for ClayBank Item Notes.

Renders clean Markdown body (with frontmatter stripped) using Flet's native GFM engine.
Supports both single-control fast rendering and block-split ListView rendering for
precise jump-target scrolling and highlight animation.

Derived from Docs/UIUX.md §6 and Docs/adr/0005-markdown-as-source-of-truth.md.
"""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    FONT_FAMILY_MONO,
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_H1,
    FONT_SIZE_LABEL,
    FONT_SIZE_TITLE_LARGE,
    SPACING_4,
    SPACING_8,
    SPACING_12,
    SPACING_16,
    create_text_style,
)
from app.views.note.note_engine import (
    NoteBlock,
    find_jump_target_block_index,
    split_markdown_into_blocks,
)


def build_markdown_style_sheet(palette: dict[str, str]) -> ft.MarkdownStyleSheet:
    """Construct token-conforming MarkdownStyleSheet for light and dark themes."""
    return ft.MarkdownStyleSheet(
        p_text_style=create_text_style(
            size=FONT_SIZE_BODY,
            color=palette["ink"],
        ),
        h1_text_style=create_text_style(
            size=FONT_SIZE_H1,
            weight=ft.FontWeight.BOLD,
            color=palette["ink"],
        ),
        h2_text_style=create_text_style(
            size=FONT_SIZE_TITLE_LARGE,
            weight=ft.FontWeight.BOLD,
            color=palette["ink"],
        ),
        h3_text_style=create_text_style(
            size=FONT_SIZE_BODY,
            weight=ft.FontWeight.BOLD,
            color=palette["ink"],
        ),
        blockquote_text_style=create_text_style(
            size=FONT_SIZE_BODY,
            color=palette["muted"],
            italic=True,
        ),
        blockquote_decoration=ft.BoxDecoration(
            border=ft.Border(left=ft.BorderSide(3.0, palette["line"])),
        ),
        blockquote_padding=ft.Padding.only(left=SPACING_12, top=SPACING_4, bottom=SPACING_4),
        a_text_style=ft.TextStyle(
            color=palette["accent"],
            decoration=ft.TextDecoration.UNDERLINE,
        ),
        code_text_style=create_text_style(
            size=FONT_SIZE_LABEL,
            is_mono=True,
            color=palette["ink"],
        ),
        codeblock_decoration=ft.BoxDecoration(
            bgcolor=palette["chip"],
            border_radius=ft.BorderRadius.all(8.0),
        ),
        codeblock_padding=ft.Padding.all(SPACING_12),
        list_bullet_text_style=create_text_style(
            size=FONT_SIZE_BODY,
            color=palette["muted"],
        ),
        checkbox_text_style=create_text_style(
            size=FONT_SIZE_BODY,
            color=palette["ink"],
        ),
        block_spacing=SPACING_12,
    )


class MarkdownNoteRenderer(ft.Container):
    """Note body Markdown renderer supporting monolithic and jump-targeted block modes."""

    def __init__(
        self,
        markdown: str,
        *,
        jump_target: str | None = None,
        on_tap_link: Callable[[str], Any] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.markdown_val = markdown
        self.jump_target_val = jump_target
        self.on_tap_link = on_tap_link
        self.theme_mode_val = theme_mode

        self.target_block_index: int | None = None
        self.target_block_key: str | None = None
        self.blocks: list[NoteBlock] = []

        palette = get_palette(theme_mode)
        self.style_sheet = build_markdown_style_sheet(palette)

        # Build view content based on whether jump_target is provided
        self.view_container = ft.Container(expand=True)
        self.rebuild_content()

        super().__init__(
            content=self.view_container,
            padding=ft.Padding.symmetric(vertical=SPACING_16),
            expand=True,
        )

    def rebuild_content(self) -> None:
        """Render monolithic Markdown or block-split ListView depending on jump_target."""
        palette = get_palette(self.theme_mode_val)

        if not self.jump_target_val:
            # Standard fast single-control render
            self.markdown_control = ft.Markdown(
                value=self.markdown_val,
                extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
                selectable=True,
                auto_follow_links=False,
                on_tap_link=self._handle_tap_link,
                md_style_sheet=self.style_sheet,
            )
            self.view_container.content = self.markdown_control
            self.target_block_index = None
            self.target_block_key = None
            self.blocks = []
        else:
            # Block-split rendering for anchor/timestamp jump targeting
            self.blocks = split_markdown_into_blocks(self.markdown_val)
            self.target_block_index = find_jump_target_block_index(self.blocks, self.jump_target_val)

            block_controls: list[ft.Control] = []
            for i, block in enumerate(self.blocks):
                is_target = (i == self.target_block_index)
                if is_target:
                    self.target_block_key = block.key

                md_block = ft.Markdown(
                    value=block.content,
                    extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
                    selectable=True,
                    auto_follow_links=False,
                    on_tap_link=self._handle_tap_link,
                    md_style_sheet=self.style_sheet,
                    shrink_wrap=True,
                )

                # Target block gets an accent-tinted background highlight
                block_wrapper = ft.Container(
                    key=block.key,
                    content=md_block,
                    bgcolor=palette["accent_bg"] if is_target else "transparent",
                    padding=ft.Padding.all(SPACING_8) if is_target else None,
                    border_radius=ft.BorderRadius.all(8.0) if is_target else None,
                    border=ft.Border.all(1.0, palette["accent"]) if is_target else None,
                )
                block_controls.append(block_wrapper)

            self.list_view = ft.ListView(
                controls=block_controls,
                spacing=SPACING_8,
                expand=True,
            )
            self.view_container.content = self.list_view

    def set_markdown(self, markdown: str, jump_target: str | None = None) -> None:
        """Update markdown content and optional jump target."""
        self.markdown_val = markdown
        self.jump_target_val = jump_target
        self.rebuild_content()

    def set_theme_mode(self, theme_mode: ft.ThemeMode | str) -> None:
        """Update styling to match theme mode."""
        self.theme_mode_val = theme_mode
        palette = get_palette(theme_mode)
        self.style_sheet = build_markdown_style_sheet(palette)
        self.rebuild_content()

    def _handle_tap_link(self, e: Any) -> None:
        """Dispatch link tap event with url payload."""
        url = getattr(e, "data", None) or str(e)
        if self.on_tap_link is not None:
            self.on_tap_link(url)
