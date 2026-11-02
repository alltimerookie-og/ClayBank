"""Unit tests for Phase 0 Step 2: Shared NavigationBar Component."""

from __future__ import annotations

import flet as ft
import pytest

from app.shell.nav import (
    TAB_COUNT,
    TAB_FOLDERS,
    TAB_INBOX,
    TAB_NAMES,
    TAB_SEARCH,
    TAB_SETTINGS,
    SharedNavigationBar,
    create_navigation_bar,
)
from app.shell.theme import DARK_PALETTE, LIGHT_PALETTE


def test_navigation_bar_exactly_four_tabs() -> None:
    """Verify NavigationBar has exactly four tabs matching canonical names."""
    nav = SharedNavigationBar()
    assert len(nav.destinations) == TAB_COUNT == 4
    labels = [d.label for d in nav.destinations]
    assert labels == list(TAB_NAMES)
    assert "Ask" not in labels
    assert labels[0] == "Inbox"
    assert labels[1] == "Folders"
    assert labels[2] == "Search"
    assert labels[3] == "Settings"


def test_navigation_bar_styling_light_mode() -> None:
    """Verify light mode background, line border, and indicator color."""
    nav = SharedNavigationBar(selected_index=TAB_INBOX)
    assert nav.selected_index == 0
    assert nav.bgcolor == LIGHT_PALETTE["background"]
    assert nav.indicator_color == LIGHT_PALETTE["accent_bg"]
    assert nav.border.top.color == LIGHT_PALETTE["line"]


def test_navigation_bar_styling_dark_mode() -> None:
    """Verify dark mode background and indicator colors."""
    nav = SharedNavigationBar(
        selected_index=TAB_FOLDERS,
        theme_mode=ft.ThemeMode.DARK,
    )
    assert nav.selected_index == 1
    assert nav.bgcolor == DARK_PALETTE["background"]
    assert nav.indicator_color == DARK_PALETTE["accent_bg"]
    assert nav.border.top.color == DARK_PALETTE["line"]


def test_navigation_bar_tab_change_callback() -> None:
    """Verify tab change event triggers on_tab_change with selected tab index."""
    changed_tab = None

    def handle_change(idx: int) -> None:
        nonlocal changed_tab
        changed_tab = idx

    nav = create_navigation_bar(selected_index=TAB_SEARCH, on_tab_change=handle_change)
    assert nav.selected_index == 2

    # Simulate on_change event from Flet control
    class MockEvent:
        def __init__(self, index: int) -> None:
            self.control = ft.NavigationBar(selected_index=index)

    nav.on_change(MockEvent(TAB_SETTINGS))
    assert changed_tab == TAB_SETTINGS


def test_navigation_bar_invalid_index() -> None:
    """Verify attempting to initialize with invalid tab index raises ValueError."""
    with pytest.raises(ValueError):
        SharedNavigationBar(selected_index=5)

    with pytest.raises(ValueError):
        SharedNavigationBar(selected_index=-1)
