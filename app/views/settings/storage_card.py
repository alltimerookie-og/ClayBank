"""Storage usage display card for ClayBank Settings.

Presents split library and local-model storage consumption.
Derived from Docs/Phases.md Phase 7, Docs/Design.md §8, Docs/UIUX.md §11, and Prototype v2.
"""

from __future__ import annotations

import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_MUTED,
    FONT_SIZE_TITLE,
    MIN_TOUCH_TARGET,
    SPACING_12,
)
from app.ui.card import ClayCard


def format_storage_size(byte_count: int | float | None) -> str:
    """Format a byte count into a human-readable storage string (B, KB, MB, GB)."""
    if byte_count is None:
        return "0 B"
    try:
        val = float(byte_count)
    except (ValueError, TypeError):
        return "0 B"

    if val <= 0:
        return "0 B"

    kb = 1024.0
    mb = 1024.0 * kb
    gb = 1024.0 * mb

    if val < kb:
        return f"{int(val)} B"
    elif val < mb:
        size_kb = val / kb
        return f"{size_kb:.1f} KB" if size_kb < 10 else f"{int(round(size_kb))} KB"
    elif val < gb:
        size_mb = val / mb
        return f"{size_mb:.1f} MB" if size_mb < 10 and not size_mb.is_integer() else f"{int(round(size_mb))} MB"
    else:
        size_gb = val / gb
        formatted = f"{size_gb:.1f}"
        if formatted.endswith(".0"):
            formatted = formatted[:-2]
        return f"{formatted} GB"


def format_split_storage(library_bytes: int | None, local_model_bytes: int | None) -> str:
    """Format combined split storage string: 'Library <size> · Local model <size>'."""
    lib_str = format_storage_size(library_bytes)
    model_str = format_storage_size(local_model_bytes)
    return f"Library {lib_str} · Local model {model_str}"


class StorageUsedCard(ClayCard):
    """Settings card displaying split storage usage between Library and Local model."""

    def __init__(
        self,
        *,
        library_bytes: int | None = 4 * 1024 * 1024,  # Default 4 MB
        local_model_bytes: int | None = int(1.1 * 1024 * 1024 * 1024),  # Default 1.1 GB
        custom_display_text: str | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
        width: float | None = None,
    ) -> None:
        self.theme_mode_val = theme_mode
        self._library_bytes = library_bytes
        self._local_model_bytes = local_model_bytes
        self._custom_display_text = custom_display_text

        palette = get_palette(theme_mode)

        self.title_text = ft.Text(
            value="Storage used",
            size=FONT_SIZE_TITLE,
            weight=ft.FontWeight.W_700,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
        )

        display_val = custom_display_text or format_split_storage(library_bytes, local_model_bytes)
        self.value_text = ft.Text(
            value=display_val,
            size=FONT_SIZE_BODY,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
            no_wrap=True,
        )

        content_row = ft.Row(
            controls=[
                self.title_text,
                self.value_text,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        super().__init__(
            content=content_row,
            padding=SPACING_12,
            theme_mode=theme_mode,
            width=width,
        )

    def set_storage(self, library_bytes: int | None, local_model_bytes: int | None) -> None:
        """Dynamically update storage values and refreshed display text."""
        self._library_bytes = library_bytes
        self._local_model_bytes = local_model_bytes
        self._custom_display_text = None
        self.value_text.value = format_split_storage(library_bytes, local_model_bytes)

    def set_custom_text(self, text: str) -> None:
        """Override storage text with a custom label."""
        self._custom_display_text = text
        self.value_text.value = text
