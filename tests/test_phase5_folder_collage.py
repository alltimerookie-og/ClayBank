"""Unit tests for FolderCoverCollage component (Phase 5 deliverable P5-01)."""

import flet as ft
import pytest

from app.shell.theme import COVER_GRADIENTS
from app.views.folders.folder_collage import (
    DEFAULT_COLLAGE_GAP,
    DEFAULT_COLLAGE_HEIGHT,
    DEFAULT_COLLAGE_RADIUS,
    FolderCoverCollage,
    resolve_gradient_keys,
)


def test_resolve_gradient_keys_deterministic():
    """Verify that resolving gradient keys for the same seed is deterministic."""
    folder_id = "018f4c1a-0000-7de6-9c8e-000000000004"
    keys_1 = resolve_gradient_keys(seed=folder_id)
    keys_2 = resolve_gradient_keys(seed=folder_id)

    assert len(keys_1) == 4
    assert keys_1 == keys_2
    for k in keys_1:
        assert k in COVER_GRADIENTS


def test_resolve_gradient_keys_explicit_override():
    """Verify explicit gradient keys are respected."""
    custom = ["g1", "g4", "g2", "g1"]
    res = resolve_gradient_keys(explicit_keys=custom)
    assert res == custom


def test_resolve_gradient_keys_explicit_fallback():
    """Verify invalid explicit keys fall back to g1."""
    custom = ["unknown_1", "g3", "invalid_key", "g2"]
    res = resolve_gradient_keys(explicit_keys=custom)
    assert res == ["g1", "g3", "g1", "g2"]


def test_folder_cover_collage_structure():
    """Verify FolderCoverCollage creates a 2x2 grid with 4 gradient cells."""
    collage = FolderCoverCollage(
        folder_id="018f4c1a-0000-7de6-9c8e-000000000004",
        folder_name="Cooking",
    )

    assert collage.height == DEFAULT_COLLAGE_HEIGHT
    assert collage.clip_behavior == ft.ClipBehavior.HARD_EDGE
    assert collage.border_radius is not None

    grid = collage.content
    assert isinstance(grid, ft.Column)
    assert len(grid.controls) == 2
    assert grid.spacing == DEFAULT_COLLAGE_GAP

    row_top = grid.controls[0]
    row_bottom = grid.controls[1]
    assert isinstance(row_top, ft.Row)
    assert isinstance(row_bottom, ft.Row)
    assert len(row_top.controls) == 2
    assert len(row_bottom.controls) == 2

    for cell in row_top.controls + row_bottom.controls:
        assert isinstance(cell, ft.Container)
        assert isinstance(cell.gradient, ft.LinearGradient)
        assert len(cell.gradient.colors) == 2


def test_folder_cover_collage_custom_dimensions():
    """Verify custom width, height, and gap configuration."""
    collage = FolderCoverCollage(
        folder_name="Custom",
        width=120.0,
        height=80.0,
        border_radius=14.0,
        gap=4.0,
    )

    assert collage.width == 120.0
    assert collage.height == 80.0
    grid = collage.content
    assert isinstance(grid, ft.Column)
    assert grid.spacing == 4.0


def test_folder_cover_collage_theme_support():
    """Verify collage renders cleanly in dark theme mode."""
    collage = FolderCoverCollage(
        folder_id="018f4c1a-0000-7de6-9c8e-000000000005",
        theme_mode=ft.ThemeMode.DARK,
    )
    assert collage is not None
    assert len(collage.gradient_keys) == 4
