"""Shared 4-tab NavigationBar component for the ClayBank application shell.

Derived from Docs/Rules.md §3, Docs/Design.md §4, and Prototype v2.
"""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from app.shell.theme import get_palette

TAB_INBOX = 0
TAB_FOLDERS = 1
TAB_SEARCH = 2
TAB_SETTINGS = 3

TAB_COUNT = 4
TAB_NAMES = ("Inbox", "Folders", "Search", "Settings")


class SharedNavigationBar(ft.NavigationBar):
    """Canonical 4-tab bottom navigation bar for ClayBank.

    Hard rule: Exactly 4 tabs (Inbox, Folders, Search, Settings).
    Ask is accessed from Search header or folder menus; Ask is never a tab.
    """

    def __init__(
        self,
        *,
        selected_index: int = TAB_INBOX,
        on_tab_change: Callable[[int], None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        if not (0 <= selected_index < TAB_COUNT):
            raise ValueError(f"selected_index must be between 0 and {TAB_COUNT - 1}, got {selected_index}")

        self.on_tab_change = on_tab_change
        palette = get_palette(theme_mode)

        destinations = [
            ft.NavigationBarDestination(
                icon=ft.Icons.INBOX_OUTLINED,
                selected_icon=ft.Icons.INBOX,
                label=TAB_NAMES[TAB_INBOX],
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.FOLDER_OUTLINED,
                selected_icon=ft.Icons.FOLDER,
                label=TAB_NAMES[TAB_FOLDERS],
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.SEARCH_ROUNDED,
                selected_icon=ft.Icons.SEARCH_ROUNDED,
                label=TAB_NAMES[TAB_SEARCH],
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.SETTINGS_OUTLINED,
                selected_icon=ft.Icons.SETTINGS,
                label=TAB_NAMES[TAB_SETTINGS],
            ),
        ]

        def _handle_change(e: Any) -> None:
            idx = int(e.control.selected_index)
            if self.on_tab_change is not None:
                self.on_tab_change(idx)

        super().__init__(
            destinations=destinations,
            selected_index=selected_index,
            bgcolor=palette["background"],
            indicator_color=palette["accent_bg"],
            border=ft.Border(top=ft.BorderSide(width=1.0, color=palette["line"])),
            on_change=_handle_change,
        )


def create_navigation_bar(
    selected_index: int = TAB_INBOX,
    on_tab_change: Callable[[int], None] | None = None,
    *,
    theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
) -> SharedNavigationBar:
    """Convenience factory function creating a standardized SharedNavigationBar."""
    return SharedNavigationBar(
        selected_index=selected_index,
        on_tab_change=on_tab_change,
        theme_mode=theme_mode,
    )
