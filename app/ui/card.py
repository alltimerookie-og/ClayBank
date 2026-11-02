"""Reusable card and container components following ClayBank design tokens.

Derived from Docs/Design.md §4 and Prototype v2 (.card, .sheet).
"""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import CARD_RADIUS, SHEET_RADIUS, SPACING_12, SPACING_18


class ClayCard(ft.Container):
    """Reusable 16 px rounded surface with subtle shadow and border."""

    def __init__(
        self,
        content: ft.Control | None = None,
        *,
        padding: float = SPACING_12,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
        on_click: Callable[[Any], None] | None = None,
        width: float | None = None,
        height: float | None = None,
        expand: bool | int | None = None,
    ) -> None:
        palette = get_palette(theme_mode)
        super().__init__(
            content=content,
            bgcolor=palette["card"],
            border_radius=ft.BorderRadius.all(CARD_RADIUS),
            border=ft.Border.all(width=1.0, color=palette["line"]),
            padding=ft.Padding.all(padding),
            shadow=ft.BoxShadow(
                spread_radius=0.0,
                blur_radius=6.0,
                offset=ft.Offset(0, 2),
                color="rgba(0,0,0,0.06)",
            ),
            width=width,
            height=height,
            expand=expand,
            on_click=on_click,
        )


class ClaySheet(ft.Container):
    """Reusable 24 px rounded container for bottom sheets."""

    def __init__(
        self,
        content: ft.Control | None = None,
        *,
        padding: float = SPACING_18,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
        width: float | None = None,
        height: float | None = None,
        expand: bool | int | None = None,
    ) -> None:
        palette = get_palette(theme_mode)
        super().__init__(
            content=content,
            bgcolor=palette["card"],
            border_radius=ft.BorderRadius.only(
                top_left=SHEET_RADIUS,
                top_right=SHEET_RADIUS,
                bottom_left=0.0,
                bottom_right=0.0,
            ),
            border=ft.Border.all(width=1.0, color=palette["line"]),
            padding=ft.Padding.all(padding),
            shadow=ft.BoxShadow(
                spread_radius=0.0,
                blur_radius=12.0,
                offset=ft.Offset(0, -4),
                color="rgba(0,0,0,0.10)",
            ),
            width=width,
            height=height,
            expand=expand,
        )
