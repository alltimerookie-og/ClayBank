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
    SPACING_4,
    SPACING_8,
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


class PlatformChip(ft.Container):
    """Muted, informational chip identifying source platform (non-interactive)."""

    def __init__(
        self,
        platform: str,
        *,
        prefix: str = "",
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.platform = platform
        self.prefix = prefix
        palette = get_palette(theme_mode)

        display_text = f"{prefix}{platform}" if prefix else platform

        text_control = ft.Text(
            value=display_text,
            size=FONT_SIZE_MICRO,
            weight=ft.FontWeight.W_500,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
            no_wrap=True,
        )

        super().__init__(
            content=text_control,
            bgcolor="transparent",
            border=None,
            padding=ft.Padding.symmetric(horizontal=SPACING_10, vertical=SPACING_10),
            alignment=ft.Alignment(0, 0),
            height=MIN_TOUCH_TARGET,
            tooltip=f"Source: {platform}",
            theme_mode=theme_mode if isinstance(theme_mode, ft.ThemeMode) else None,
        )


class TagChip(ft.Container):
    """Filled chip for flat tags, supporting filter-in-place and optional deletion."""

    def __init__(
        self,
        name: str,
        *,
        on_click: Callable[[Any], None] | None = None,
        on_delete: Callable[[Any], None] | None = None,
        selected: bool = False,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        clean_name = name.strip()
        formatted_name = clean_name if clean_name.startswith("#") else f"#{clean_name}"
        self.tag_name = formatted_name
        self.selected = selected
        self.on_delete = on_delete

        palette = get_palette(theme_mode)

        if selected:
            bg_color = palette["accent_bg"]
            text_color = palette["accent_ink"]
            border = ft.Border.all(width=1.0, color=palette["accent"])
        else:
            bg_color = palette["chip"]
            text_color = palette["chip_ink"]
            border = None

        text_control = ft.Text(
            value=formatted_name,
            size=FONT_SIZE_MICRO,
            weight=ft.FontWeight.W_600,
            color=text_color,
            font_family=FONT_FAMILY_UI,
            no_wrap=True,
        )

        if on_delete is not None:
            delete_btn = ft.IconButton(
                icon=ft.Icons.CLOSE_ROUNDED,
                icon_size=14.0,
                icon_color=text_color,
                on_click=on_delete,
                tooltip=f"Remove {formatted_name}",
                width=24.0,
                height=24.0,
                padding=ft.Padding.all(0),
            )
            content_control = ft.Row(
                controls=[text_control, delete_btn],
                spacing=SPACING_4,
                alignment=ft.MainAxisAlignment.CENTER,
                tight=True,
            )
        else:
            content_control = text_control

        super().__init__(
            content=content_control,
            bgcolor=bg_color,
            border=border,
            border_radius=ft.BorderRadius.all(PILL_RADIUS),
            padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
            alignment=ft.Alignment(0, 0),
            height=MIN_TOUCH_TARGET,
            on_click=on_click,
            tooltip=f"Tag: {formatted_name}",
            theme_mode=theme_mode if isinstance(theme_mode, ft.ThemeMode) else None,
        )


class CitationChip(ft.Container):
    """Citation or jump-target chip opening a note source at a specific offset."""

    def __init__(
        self,
        label: str,
        *,
        target_offset: str | None = None,
        save_id: str | None = None,
        confidence: float | None = None,
        is_jump: bool = False,
        on_click: Callable[[Any], None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.label = label
        self.target_offset = target_offset
        self.save_id = save_id
        self.confidence = confidence
        self.is_jump = is_jump

        palette = get_palette(theme_mode)

        display_text = label
        if confidence is not None:
            pct = int(confidence * 100) if confidence <= 1.0 else int(confidence)
            display_text = f"{display_text} · {pct}%"

        if is_jump:
            bg_color = "transparent"
            border = ft.Border.all(width=1.0, color=palette["line"])
            text_color = palette["ink"]
        else:
            bg_color = palette["chip"]
            border = None
            text_color = palette["chip_ink"]

        text_control = ft.Text(
            value=display_text,
            size=FONT_SIZE_MICRO,
            weight=ft.FontWeight.W_600,
            color=text_color,
            font_family=FONT_FAMILY_UI,
            no_wrap=True,
        )

        super().__init__(
            content=text_control,
            bgcolor=bg_color,
            border=border,
            border_radius=ft.BorderRadius.all(PILL_RADIUS),
            padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
            alignment=ft.Alignment(0, 0),
            height=MIN_TOUCH_TARGET,
            on_click=on_click,
            tooltip=f"Citation: {display_text}" + (f" ({target_offset})" if target_offset else ""),
            theme_mode=theme_mode if isinstance(theme_mode, ft.ThemeMode) else None,
        )




