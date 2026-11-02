"""Typed chip components adhering to ClayBank design system.

Derived from Docs/Design.md §4, §7.4, and Prototype v2.
"""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    FONT_FAMILY_UI,
    FONT_SIZE_MICRO,
    MIN_TOUCH_TARGET,
    PILL_RADIUS,
    SPACING_10,
    SPACING_12,
)


class FolderChip(ft.Container):
    """Outlined, path-based chip for folder identity and navigation."""

    def __init__(
        self,
        path: str,
        *,
        on_click: Callable[[Any], None] | None = None,
        prefix: str = "→ ",
        count: int | None = None,
        chevron: bool = False,
        is_active: bool = False,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.chip_path = path
        self.prefix = prefix
        self.count = count
        self.chevron = chevron
        self.is_active = is_active

        palette = get_palette(theme_mode)

        # Formulate display label
        if count is not None and count > 0:
            suffix = " ›" if chevron else ""
            label_text = f"{path} {count}{suffix}"
        elif chevron:
            label_text = f"{path} ›"
        elif prefix:
            label_text = f"{prefix}{path}"
        else:
            label_text = path

        text_color = palette["accent_ink"]
        bg_color = palette["accent_bg"] if is_active else "transparent"
        border_color = palette["accent"]

        text_control = ft.Text(
            value=label_text,
            size=FONT_SIZE_MICRO,
            weight=ft.FontWeight.W_600,
            color=text_color,
            font_family=FONT_FAMILY_UI,
            no_wrap=True,
        )

        super().__init__(
            content=text_control,
            bgcolor=bg_color,
            border=ft.Border.all(width=1.0, color=border_color),
            border_radius=ft.BorderRadius.all(PILL_RADIUS),
            padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_10),
            alignment=ft.Alignment(0, 0),
            height=MIN_TOUCH_TARGET,
            on_click=on_click,
            tooltip=f"Folder: {path}",
            theme_mode=theme_mode if isinstance(theme_mode, ft.ThemeMode) else None,
        )

