"""Unit tests for P4-04: Markdown Note Renderer."""

from __future__ import annotations

import flet as ft

from app.views.note.note_renderer import MarkdownNoteRenderer, build_markdown_style_sheet
from app.shell.theme import get_palette

SAMPLE_MARKDOWN = """# Creamy garlic pasta

## Overview
A 20 minute pasta with a garlic cream sauce.

## Key points
- Salt the water well
- Fry garlic on low heat
- [Link](https://example.com/pasta)

## Transcript
> 0:08 Start with well salted water.
> 0:42 Now add the cream.
"""


def test_markdown_renderer_standard_monolithic() -> None:
    """Verify default rendering uses a single ft.Markdown control."""
    renderer = MarkdownNoteRenderer(markdown=SAMPLE_MARKDOWN)

    assert isinstance(renderer.view_container.content, ft.Markdown)
    md_control: ft.Markdown = renderer.view_container.content
    assert md_control.value == SAMPLE_MARKDOWN
    assert md_control.selectable
    assert md_control.extension_set == ft.MarkdownExtensionSet.GITHUB_FLAVORED
    assert md_control.md_style_sheet is not None
    assert renderer.target_block_index is None


def test_markdown_renderer_jump_target_timestamp() -> None:
    """Verify supplying a timestamp jump target splits into blocks and highlights target."""
    renderer = MarkdownNoteRenderer(markdown=SAMPLE_MARKDOWN, jump_target="0:42")

    assert isinstance(renderer.view_container.content, ft.ListView)
    list_view: ft.ListView = renderer.view_container.content
    assert len(list_view.controls) >= 4
    assert renderer.target_block_index is not None

    # Check target block container highlight
    target_container = list_view.controls[renderer.target_block_index]
    assert isinstance(target_container, ft.Container)
    palette = get_palette(ft.ThemeMode.LIGHT)
    assert target_container.bgcolor == palette["accent_bg"]
    assert "0:42" in renderer.blocks[renderer.target_block_index].content


def test_markdown_renderer_jump_target_heading_anchor() -> None:
    """Verify supplying a heading anchor jump target highlights matching heading block."""
    renderer = MarkdownNoteRenderer(markdown=SAMPLE_MARKDOWN, jump_target="#key-points")

    assert isinstance(renderer.view_container.content, ft.ListView)
    assert renderer.target_block_index is not None
    target_block = renderer.blocks[renderer.target_block_index]
    assert target_block.anchor == "key-points"


def test_markdown_renderer_tap_link_callback() -> None:
    """Verify link tap callback receives clicked url."""
    tapped_url: str | None = None

    def on_link(url: str) -> None:
        nonlocal tapped_url
        tapped_url = url

    renderer = MarkdownNoteRenderer(markdown=SAMPLE_MARKDOWN, on_tap_link=on_link)

    # Simulate link event
    class MockEvent:
        data = "https://example.com/pasta"

    renderer._handle_tap_link(MockEvent())
    assert tapped_url == "https://example.com/pasta"


def test_markdown_renderer_dynamic_update() -> None:
    """Verify set_markdown can toggle from monolithic to jump-target mode."""
    renderer = MarkdownNoteRenderer(markdown=SAMPLE_MARKDOWN)
    assert isinstance(renderer.view_container.content, ft.Markdown)

    # Switch to jump mode
    renderer.set_markdown(SAMPLE_MARKDOWN, jump_target="0:08")
    assert isinstance(renderer.view_container.content, ft.ListView)
    assert renderer.target_block_index is not None

    # Switch back to monolithic
    renderer.set_markdown(SAMPLE_MARKDOWN, jump_target=None)
    assert isinstance(renderer.view_container.content, ft.Markdown)


def test_markdown_renderer_style_sheet_palette() -> None:
    """Verify style sheet creation handles dark mode palette."""
    palette = get_palette(ft.ThemeMode.DARK)
    style_sheet = build_markdown_style_sheet(palette)

    assert style_sheet.p_text_style is not None
    assert style_sheet.p_text_style.color == palette["ink"]
    assert style_sheet.a_text_style is not None
    assert style_sheet.a_text_style.color == palette["accent"]
    assert style_sheet.code_text_style is not None
    assert style_sheet.code_text_style.color == palette["ink"]

