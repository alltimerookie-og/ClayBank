"""Unit tests for Phase 0 Step 2: Typed Chip Components."""

from __future__ import annotations

import flet as ft

from app.shell.theme import DARK_PALETTE, LIGHT_PALETTE
from app.shell.tokens import MIN_TOUCH_TARGET, PILL_RADIUS
from app.ui.chips import FolderChip


def test_folder_chip_visual_properties() -> None:
    """Verify FolderChip outlined styling and path presentation."""
    chip = FolderChip(path="Cooking / Pasta")
    assert chip.bgcolor == "transparent"
    assert chip.border.top.color == LIGHT_PALETTE["accent"]
    assert chip.border_radius.top_left == PILL_RADIUS
    assert chip.height == MIN_TOUCH_TARGET
    assert isinstance(chip.content, ft.Text)
    assert chip.content.value == "→ Cooking / Pasta"
    assert chip.content.color == LIGHT_PALETTE["accent_ink"]


def test_folder_chip_child_navigation_with_count() -> None:
    """Verify FolderChip child navigation formatting (e.g. Pasta 6 ›)."""
    chip = FolderChip(path="Pasta", count=6, chevron=True)
    assert chip.content.value == "Pasta 6 ›"


def test_folder_chip_dark_mode() -> None:
    """Verify FolderChip theme adaptation for dark mode."""
    chip = FolderChip(
        path="Fitness",
        theme_mode=ft.ThemeMode.DARK,
    )
    assert chip.border.top.color == DARK_PALETTE["accent"]
    assert chip.content.color == DARK_PALETTE["accent_ink"]


def test_folder_chip_click_callback() -> None:
    """Verify FolderChip invokes on_click callback."""
    clicked = False

    def handle_click(_e: ft.ControlEvent) -> None:
        nonlocal clicked
        clicked = True

    chip = FolderChip(path="Research", on_click=handle_click)
    assert chip.on_click is not None
    chip.on_click(None)
    assert clicked is True
