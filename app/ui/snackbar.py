"""Standardized Undo SnackBar component for organizational actions.

Derived from Docs/Design.md §7.2, §7.8, Docs/UIUX.md §189, and Prototype v2.
"""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import FONT_FAMILY_UI, FONT_SIZE_BODY

DEFAULT_SNACKBAR_DURATION_MS = 3600


class UndoSnackBar(ft.SnackBar):
    """High-contrast, floating SnackBar providing feedback and guaranteed 1-tap Undo."""

    def __init__(
        self,
        message: str,
        *,
        on_undo: Callable[[Any], None] | None = None,
        duration_ms: int = DEFAULT_SNACKBAR_DURATION_MS,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.message_text = message
        self.on_undo = on_undo
        self.duration_ms = duration_ms

        palette = get_palette(theme_mode)

        # Inverted high-contrast container: ink background with bg text
        content_control = ft.Text(
            value=message,
            size=FONT_SIZE_BODY,
            weight=ft.FontWeight.W_600,
            color=palette["background"],
            font_family=FONT_FAMILY_UI,
        )

        super().__init__(
            content=content_control,
            bgcolor=palette["ink"],
            duration=duration_ms,
            behavior=ft.SnackBarBehavior.FLOATING,
            action="Undo" if on_undo is not None else None,
            on_action=on_undo,
            open=True,
        )

    @property
    def message(self) -> str:
        return self.message_text

    def trigger_undo(self) -> None:
        if self.on_undo is not None:
            self.on_undo(None)


def create_undo_snackbar(
    message: str,
    undo_callback: Callable[[Any], None] | None = None,
    *,
    duration_ms: int = DEFAULT_SNACKBAR_DURATION_MS,
    theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
) -> UndoSnackBar:
    """Convenience factory function creating a standardized UndoSnackBar."""
    return UndoSnackBar(
        message=message,
        on_undo=undo_callback,
        duration_ms=duration_ms,
        theme_mode=theme_mode,
    )
