"""Preference switch component for ClayBank Settings.

Reusable card row presenting a setting label and 44 px interactive switch.
Derived from Docs/Phases.md Phase 7, Docs/Design.md §8, Docs/UIUX.md §11, and Prototype v2.
"""

from __future__ import annotations

from typing import Any, Callable
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


class SettingSwitchCard(ClayCard):
    """Setting switch row housed in a ClayCard with minimum 44 px touch target."""

    def __init__(
        self,
        title: str,
        *,
        field_key: str,
        value: bool = True,
        description: str | None = None,
        on_change: Callable[[str, bool], None] | None = None,
        disabled: bool = False,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
        width: float | None = None,
    ) -> None:
        self.theme_mode_val = theme_mode
        self.title = title
        self.field_key = field_key
        self._value = value
        self.description = description
        self.on_change = on_change
        self._disabled = disabled

        palette = get_palette(theme_mode)

        # Label control
        self.title_text = ft.Text(
            value=title,
            size=FONT_SIZE_BODY,
            weight=ft.FontWeight.W_600,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
        )

        label_controls: list[ft.Control] = [self.title_text]
        if description:
            label_controls.append(
                ft.Text(
                    value=description,
                    size=FONT_SIZE_MUTED,
                    color=palette["muted"],
                    font_family=FONT_FAMILY_UI,
                )
            )

        label_col = ft.Column(
            controls=label_controls,
            spacing=2.0,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.START,
            expand=True,
        )

        def _handle_toggle(e: Any) -> None:
            new_val = bool(e.control.value)
            self._value = new_val
            if self.on_change is not None:
                self.on_change(self.field_key, new_val)

        # Switch with guaranteed >= 44 px touch target height
        self.switch_control = ft.Switch(
            value=self._value,
            on_change=_handle_toggle,
            active_color=palette["accent"],
            disabled=disabled,
            height=MIN_TOUCH_TARGET,
        )

        content_row = ft.Row(
            controls=[
                label_col,
                self.switch_control,
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

    @property
    def value(self) -> bool:
        """Current boolean value of the switch."""
        return self._value

    def set_value(self, value: bool) -> None:
        """Update switch value programmatically."""
        self._value = value
        self.switch_control.value = value

    def set_disabled(self, disabled: bool) -> None:
        """Set interactive disabled state."""
        self._disabled = disabled
        self.switch_control.disabled = disabled
