"""Unit tests for P4-05: Quick Insert Toolbar."""

from __future__ import annotations

import flet as ft

from app.views.note.editor_toolbar import QuickInsertToolbar, apply_markdown_syntax


def test_apply_markdown_syntax_heading() -> None:
    """Verify heading prepends ## to beginning of current line."""
    text = "First line\nSecond line\nThird line"
    # Cursor at character 14 (inside 'Second line')
    new_text, s, e = apply_markdown_syntax(text, "h", 14, 14)
    assert new_text == "First line\n## Second line\nThird line"


def test_apply_markdown_syntax_bold() -> None:
    """Verify bold wraps selection in ** or inserts **bold**."""
    text = "Hello world"
    # Select 'world' (chars 6 to 11)
    new_text, s, e = apply_markdown_syntax(text, "b", 6, 11)
    assert new_text == "Hello **world**"

    # Empty selection at index 5
    new_text2, s2, e2 = apply_markdown_syntax("Hello", "b", 5, 5)
    assert new_text2 == "Hello**bold**"


def test_apply_markdown_syntax_list() -> None:
    """Verify list prepends '- ' to line."""
    text = "Buy milk"
    new_text, s, e = apply_markdown_syntax(text, "list", 3, 3)
    assert new_text == "- Buy milk"


def test_apply_markdown_syntax_task() -> None:
    """Verify task prepends '- [ ] ' to line."""
    text = "Do laundry"
    new_text, s, e = apply_markdown_syntax(text, "task", 2, 2)
    assert new_text == "- [ ] Do laundry"


def test_apply_markdown_syntax_link() -> None:
    """Verify link wraps selection or inserts markdown link format."""
    text = "Visit ClayBank today"
    # Select 'ClayBank' (chars 6 to 14)
    new_text, s, e = apply_markdown_syntax(text, "link", 6, 14)
    assert new_text == "Visit [ClayBank](https://example.com) today"

    # Empty selection
    new_text2, s2, e2 = apply_markdown_syntax("", "link", 0, 0)
    assert new_text2 == "[link text](https://example.com)"


def test_quick_insert_toolbar_callbacks() -> None:
    """Verify toolbar chips dispatch corresponding action tokens."""
    actions: list[str] = []

    def on_ins(act: str) -> None:
        actions.append(act)

    toolbar = QuickInsertToolbar(on_insert=on_ins)

    toolbar.trigger_action("h")
    toolbar.trigger_action("b")
    toolbar.trigger_action("list")
    toolbar.trigger_action("task")
    toolbar.trigger_action("link")

    assert actions == ["h", "b", "list", "task", "link"]


def test_quick_insert_toolbar_dark_theme() -> None:
    """Verify dark mode initialization."""
    toolbar = QuickInsertToolbar(theme_mode=ft.ThemeMode.DARK)
    assert toolbar.theme_mode_val == ft.ThemeMode.DARK
    assert toolbar.content is not None
