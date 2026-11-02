"""Unit tests for Phase 0 Step 2: Undo SnackBar Component."""

from __future__ import annotations

import flet as ft

from app.shell.theme import DARK_PALETTE, LIGHT_PALETTE
from app.ui.snackbar import (
    DEFAULT_SNACKBAR_DURATION_MS,
    UndoSnackBar,
    create_undo_snackbar,
)


def test_undo_snackbar_default_duration() -> None:
    """Verify default duration is exactly 3600 ms as documented in prototype."""
    assert DEFAULT_SNACKBAR_DURATION_MS == 3600
    snack = UndoSnackBar(message="Filed to Cooking / Pasta")
    assert snack.duration == 3600


def test_undo_snackbar_high_contrast_light_mode() -> None:
    """Verify inverted high contrast styling in light mode (ink bg, background text)."""
    snack = UndoSnackBar(message="Note moved")
    assert snack.bgcolor == LIGHT_PALETTE["ink"]
    assert isinstance(snack.content, ft.Text)
    assert snack.content.value == "Note moved"
    assert snack.content.color == LIGHT_PALETTE["background"]
    assert snack.behavior == ft.SnackBarBehavior.FLOATING


def test_undo_snackbar_dark_mode() -> None:
    """Verify inverted high contrast styling in dark mode."""
    snack = UndoSnackBar(
        message="Tags updated",
        theme_mode=ft.ThemeMode.DARK,
    )
    assert snack.bgcolor == DARK_PALETTE["ink"]
    assert snack.content.color == DARK_PALETTE["background"]


def test_undo_snackbar_callback_invocation() -> None:
    """Verify Undo action callback execution."""
    undone = False

    def handle_undo(_e: ft.ControlEvent) -> None:
        nonlocal undone
        undone = True

    snack = create_undo_snackbar("Item deleted", undo_callback=handle_undo)
    assert snack.action == "Undo"
    assert snack.on_action is not None
    snack.on_action(None)
    assert undone is True


def test_undo_snackbar_without_callback() -> None:
    """Verify informative snackbar without undo callback has no action button."""
    snack = create_undo_snackbar("Saved locally")
    assert snack.action is None
    assert snack.on_action is None
