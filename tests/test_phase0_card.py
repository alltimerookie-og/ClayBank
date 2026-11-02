"""Unit tests for Phase 0 Step 2: Reusable Card / Container."""

from __future__ import annotations

import flet as ft

from app.shell.theme import DARK_PALETTE, LIGHT_PALETTE
from app.shell.tokens import CARD_RADIUS, SHEET_RADIUS
from app.ui.card import ClayCard, ClaySheet


def test_clay_card_default_light_theme() -> None:
    """Verify ClayCard default properties in light mode."""
    card = ClayCard(content=ft.Text("Test Card"))
    assert card.bgcolor == LIGHT_PALETTE["card"]
    assert card.border.top.color == LIGHT_PALETTE["line"]
    assert card.border_radius.top_left == CARD_RADIUS
    assert card.border_radius.bottom_right == CARD_RADIUS
    assert card.shadow is not None
    assert card.shadow.blur_radius == 6.0


def test_clay_card_dark_theme() -> None:
    """Verify ClayCard adapts colors for dark mode."""
    card = ClayCard(
        content=ft.Text("Dark Card"),
        theme_mode=ft.ThemeMode.DARK,
    )
    assert card.bgcolor == DARK_PALETTE["card"]
    assert card.border.top.color == DARK_PALETTE["line"]
    assert card.border_radius.top_left == CARD_RADIUS


def test_clay_card_interactive_click_handler() -> None:
    """Verify ClayCard accepts and retains an on_click handler."""
    clicked = False

    def on_click_handler(_e: ft.ControlEvent) -> None:
        nonlocal clicked
        clicked = True

    card = ClayCard(on_click=on_click_handler)
    assert card.on_click is not None
    card.on_click(None)
    assert clicked is True


def test_clay_sheet_radii_and_styling() -> None:
    """Verify ClaySheet 24 px top radii and styling."""
    sheet = ClaySheet(content=ft.Text("Sheet Content"))
    assert sheet.bgcolor == LIGHT_PALETTE["card"]
    assert sheet.border_radius.top_left == SHEET_RADIUS
    assert sheet.border_radius.top_right == SHEET_RADIUS
    assert sheet.border_radius.bottom_left == 0.0
    assert sheet.border_radius.bottom_right == 0.0
