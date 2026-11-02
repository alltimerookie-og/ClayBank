"""Quick Insert Toolbar for ClayBank Markdown Editor.

Provides one-tap insert chips for Markdown formatting:
- H: Prepend '## ' to current line
- B: Wrap selection in '**' or insert '**bold**'
- List: Prepend '- ' to current line
- Task: Prepend '- [ ] ' to current line
- Link: Wrap selection in '[text](https://example.com)'

Derived from Docs/UIUX.md §6 and Prototype v2 Screen 8.
"""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    FONT_FAMILY_UI,
    FONT_SIZE_LABEL,
    MIN_TOUCH_TARGET,
    PILL_RADIUS,
    SPACING_4,
    SPACING_8,
    SPACING_12,
    create_text_style,
)


def apply_markdown_syntax(
    text: str,
    action: str,
    sel_start: int = 0,
    sel_end: int = 0,
) -> tuple[str, int, int]:
    """Pure function calculating new text and cursor position after applying markdown syntax.

    Args:
        text: Current full editor text.
        action: One of 'h', 'b', 'list', 'task', 'link'.
        sel_start: Start index of selection or cursor position.
        sel_end: End index of selection or cursor position.

    Returns:
        Tuple of (new_text, new_sel_start, new_sel_end).
    """
    if sel_start < 0:
        sel_start = 0
    if sel_end < sel_start:
        sel_end = sel_start
    if sel_start > len(text):
        sel_start = len(text)
    if sel_end > len(text):
        sel_end = len(text)

    selected_text = text[sel_start:sel_end]

    # Find the beginning of the line containing sel_start
    line_start = text.rfind("\n", 0, sel_start) + 1

    act = action.lower().strip()

    if act == "b":
        # Bold
        placeholder = selected_text if selected_text else "bold"
        inserted = f"**{placeholder}**"
        new_text = text[:sel_start] + inserted + text[sel_end:]
        new_start = sel_start + 2
        new_end = new_start + len(placeholder)
        return new_text, new_start, new_end

    elif act == "l" or act == "link":
        # Link
        placeholder = selected_text if selected_text else "link text"
        inserted = f"[{placeholder}](https://example.com)"
        new_text = text[:sel_start] + inserted + text[sel_end:]
        new_start = sel_start + len(placeholder) + 3
        new_end = new_start + len("https://example.com")
        return new_text, new_start, new_end

    elif act == "h":
        # Heading 2
        prefix = "## "
        new_text = text[:line_start] + prefix + text[line_start:]
        return new_text, sel_start + len(prefix), sel_end + len(prefix)

    elif act in ("u", "list"):
        # Unordered List
        prefix = "- "
        new_text = text[:line_start] + prefix + text[line_start:]
        return new_text, sel_start + len(prefix), sel_end + len(prefix)

    elif act in ("t", "task"):
        # Task Checkbox
        prefix = "- [ ] "
        new_text = text[:line_start] + prefix + text[line_start:]
        return new_text, sel_start + len(prefix), sel_end + len(prefix)

    return text, sel_start, sel_end


class QuickInsertToolbar(ft.Container):
    """Horizontal toolbar with one-tap syntax insertion chips."""

    def __init__(
        self,
        *,
        on_insert: Callable[[str], Any] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.on_insert = on_insert
        self.theme_mode_val = theme_mode

        palette = get_palette(theme_mode)

        # Build toolbar action buttons
        self.btn_h = self._build_toolbar_chip("H", "h", is_bold=False, palette=palette)
        self.btn_b = self._build_toolbar_chip("B", "b", is_bold=True, palette=palette)
        self.btn_list = self._build_toolbar_chip("List", "list", is_bold=False, palette=palette)
        self.btn_task = self._build_toolbar_chip("Task", "task", is_bold=False, palette=palette)
        self.btn_link = self._build_toolbar_chip("Link", "link", is_bold=False, palette=palette)

        toolbar_row = ft.Row(
            controls=[
                self.btn_h,
                self.btn_b,
                self.btn_list,
                self.btn_task,
                self.btn_link,
            ],
            spacing=SPACING_8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.ADAPTIVE,
        )

        super().__init__(
            content=toolbar_row,
            padding=ft.Padding.symmetric(vertical=SPACING_4),
        )

    def _build_toolbar_chip(
        self,
        label: str,
        action: str,
        is_bold: bool,
        palette: dict[str, str],
    ) -> ft.Container:
        """Construct a touch-friendly chip for an action."""
        text_style = create_text_style(
            size=FONT_SIZE_LABEL,
            weight=ft.FontWeight.BOLD if is_bold else ft.FontWeight.W_500,
            color=palette["ink"],
        )

        return ft.Container(
            content=ft.Text(label, style=text_style),
            bgcolor=palette["chip"],
            padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
            border_radius=ft.BorderRadius.all(PILL_RADIUS),
            alignment=ft.Alignment(0, 0),
            height=36.0,
            on_click=lambda _: self.trigger_action(action),
            tooltip=f"Insert {label}",
        )

    def trigger_action(self, action: str) -> None:
        """Dispatch action token to callback."""
        if self.on_insert is not None:
            self.on_insert(action)
