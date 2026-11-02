"""Unit tests for P4-03: Note Properties Grid."""

from __future__ import annotations

import flet as ft

from app.views.note.properties_grid import PropertiesGrid


def test_properties_grid_full_frontmatter() -> None:
    """Verify all frontmatter fields render in the two-column grid."""
    fm = {
        "source": "Instagram",
        "channel": "@chefmara",
        "video_url": "https://instagram.com/reel/123",
        "duration": 58,
        "published": "2026-10-03",
        "saved": "2026-10-31",
        "folder": "Cooking / Pasta",
        "tags": ["recipe", "pasta", "dinner"],
    }
    grid = PropertiesGrid(frontmatter=fm)

    # 8 rows built
    rows = grid.rows_column.controls
    assert len(rows) == 8

    # Verify 96px label column
    for row in rows:
        assert isinstance(row, ft.Row)
        label_container = row.controls[0]
        assert isinstance(label_container, ft.Container)
        assert label_container.width == 96.0


def test_properties_grid_live_folder_callback() -> None:
    """Verify folder control emits folder edit callback on tap."""
    folder_invoked = False

    def on_folder() -> None:
        nonlocal folder_invoked
        folder_invoked = True

    fm = {"folder": "Cooking / Pasta"}
    grid = PropertiesGrid(frontmatter=fm, on_edit_folder=on_folder)

    grid._handle_edit_folder()
    assert folder_invoked


def test_properties_grid_live_tags_callback() -> None:
    """Verify tags control emits tags edit callback on tap."""
    tags_invoked = False

    def on_tags() -> None:
        nonlocal tags_invoked
        tags_invoked = True

    fm = {"tags": ["recipe", "pasta"]}
    grid = PropertiesGrid(frontmatter=fm, on_edit_tags=on_tags)

    grid._handle_edit_tags()
    assert tags_invoked


def test_properties_grid_url_click_callback() -> None:
    """Verify video url emits open url callback."""
    clicked_url: str | None = None

    def on_url(url: str) -> None:
        nonlocal clicked_url
        clicked_url = url

    fm = {"video_url": "https://example.com/video"}
    grid = PropertiesGrid(frontmatter=fm, on_open_url=on_url)

    grid._handle_url_click("https://example.com/video")
    assert clicked_url == "https://example.com/video"


def test_properties_grid_missing_optional_fields() -> None:
    """Verify missing fields do not create empty or crashed rows."""
    fm = {
        "source": "YouTube",
        "folder": None,
        "tags": [],
    }
    grid = PropertiesGrid(frontmatter=fm)
    rows = grid.rows_column.controls

    # Should have source, folder ((Unfiled)), tags ((None)) -> 3 rows
    assert len(rows) == 3


def test_properties_grid_dynamic_update() -> None:
    """Verify set_frontmatter dynamically rebuilds rows."""
    grid = PropertiesGrid(frontmatter={"source": "YouTube"})
    assert len(grid.rows_column.controls) == 3  # source, folder, tags

    grid.set_frontmatter({
        "source": "Instagram",
        "channel": "@chefmara",
        "folder": "Cooking",
        "tags": ["pasta"],
    })
    # source, channel, folder, tags -> 4 rows
    assert len(grid.rows_column.controls) == 4


def test_properties_grid_dark_mode() -> None:
    """Verify dark mode initialization."""
    grid = PropertiesGrid(
        frontmatter={"source": "Instagram", "folder": "Cooking"},
        theme_mode=ft.ThemeMode.DARK,
    )
    assert grid.theme_mode_val == ft.ThemeMode.DARK
    assert len(grid.rows_column.controls) >= 2

