"""Unit tests for P2-01: Application Shell Layout."""

from __future__ import annotations

import flet as ft
import pytest

from app.shell.app_shell import AppShellLayout, TabPlaceholderView
from app.shell.nav import TAB_COUNT, TAB_FOLDERS, TAB_INBOX, TAB_SEARCH, TAB_SETTINGS
from app.shell.theme import DARK_PALETTE, LIGHT_PALETTE


def test_app_shell_defaults() -> None:
    """Verify app shell initializes to Inbox with exactly 4 tabs and matching header."""
    shell = AppShellLayout()
    assert shell.selected_index == TAB_INBOX
    assert shell.header.title_text.value == "Inbox"
    assert len(shell.tab_views) == TAB_COUNT
    assert TAB_INBOX in shell.tab_views
    assert TAB_FOLDERS in shell.tab_views
    assert TAB_SEARCH in shell.tab_views
    assert TAB_SETTINGS in shell.tab_views
    assert shell.content_area.content is shell.tab_views[TAB_INBOX]
    assert shell.nav_bar.selected_index == TAB_INBOX


def test_app_shell_tab_switching() -> None:
    """Verify switching tabs updates index, header title, content area, and callback."""
    changed_indices: list[int] = []

    def on_change(idx: int) -> None:
        changed_indices.append(idx)

    shell = AppShellLayout(on_tab_change=on_change)

    # Switch to Folders (1)
    shell.set_tab(TAB_FOLDERS)
    assert shell.selected_index == TAB_FOLDERS
    assert shell.header.title_text.value == "Folders"
    assert shell.content_area.content is shell.tab_views[TAB_FOLDERS]
    assert shell.nav_bar.selected_index == TAB_FOLDERS

    # Switch to Search (2)
    shell.set_tab(TAB_SEARCH)
    assert shell.selected_index == TAB_SEARCH
    assert shell.header.title_text.value == "Search"
    assert shell.content_area.content is shell.tab_views[TAB_SEARCH]

    # Switch to Settings (3)
    shell.set_tab(TAB_SETTINGS)
    assert shell.selected_index == TAB_SETTINGS
    assert shell.header.title_text.value == "Settings"
    assert shell.content_area.content is shell.tab_views[TAB_SETTINGS]

    assert changed_indices == [TAB_FOLDERS, TAB_SEARCH, TAB_SETTINGS]


def test_app_shell_invalid_tab_index() -> None:
    """Verify out-of-range tab index raises ValueError."""
    shell = AppShellLayout()
    with pytest.raises(ValueError):
        shell.set_tab(-1)
    with pytest.raises(ValueError):
        shell.set_tab(4)


def test_app_shell_state_preservation() -> None:
    """Verify tab view instances are preserved when switching back and forth."""
    shell = AppShellLayout()
    inbox_instance = shell.tab_views[TAB_INBOX]
    folders_instance = shell.tab_views[TAB_FOLDERS]

    shell.set_tab(TAB_FOLDERS)
    assert shell.content_area.content is folders_instance

    shell.set_tab(TAB_INBOX)
    assert shell.content_area.content is inbox_instance
    assert shell.tab_views[TAB_INBOX] is inbox_instance


def test_app_shell_add_link_trigger() -> None:
    """Verify Add Link button invokes callback from any tab."""
    invoked = False

    def on_add() -> None:
        nonlocal invoked
        invoked = True

    shell = AppShellLayout(on_add_link=on_add)
    # Trigger from inbox
    shell.trigger_add_link()
    assert invoked

    # Trigger from folders tab
    invoked = False
    shell.set_tab(TAB_FOLDERS)
    shell.trigger_add_link()
    assert invoked


def test_app_shell_set_inbox_view() -> None:
    """Verify injecting real inbox view updates shell state."""
    shell = AppShellLayout()
    custom_inbox = ft.Container(content=ft.Text("Custom Real Inbox"))
    shell.set_inbox_view(custom_inbox)

    assert shell.tab_views[TAB_INBOX] is custom_inbox
    assert shell.content_area.content is custom_inbox

    # Switch away and back
    shell.set_tab(TAB_SETTINGS)
    assert shell.content_area.content is not custom_inbox
    shell.set_tab(TAB_INBOX)
    assert shell.content_area.content is custom_inbox


def test_app_shell_theme_mode_update() -> None:
    """Verify updating theme mode updates colors to dark palette."""
    shell = AppShellLayout(theme_mode=ft.ThemeMode.LIGHT)
    assert shell.header.bgcolor == LIGHT_PALETTE["background"]

    shell.set_theme_mode(ft.ThemeMode.DARK)
    assert shell.header.bgcolor == DARK_PALETTE["background"]
    assert shell.header.title_text.color == DARK_PALETTE["ink"]
    assert shell.header.add_button.icon_color == DARK_PALETTE["accent"]
    assert shell.content_area.bgcolor == DARK_PALETTE["background"]
    assert shell.nav_bar.bgcolor == DARK_PALETTE["background"]

