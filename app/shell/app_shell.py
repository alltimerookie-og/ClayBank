"""Application Shell Layout for ClayBank.

Hosts the persistent 4-tab navigation, dynamic context header, global Add Link action,
and swaps active tab content while preserving tab states.

Derived from Docs/Rules.md §3, Docs/Design.md §4, Docs/UIUX.md §4.1, and Prototype v2.
"""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from app.shell.icons import IconName, get_icon
from app.shell.nav import (
    TAB_COUNT,
    TAB_FOLDERS,
    TAB_INBOX,
    TAB_NAMES,
    TAB_SEARCH,
    TAB_SETTINGS,
    SharedNavigationBar,
)
from app.shell.theme import get_palette
from app.shell.tokens import (
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_H1,
    FONT_SIZE_TITLE,
    FONT_SIZE_TITLE_LARGE,
    MIN_TOUCH_TARGET,
    SPACING_8,
    SPACING_12,
    SPACING_16,
    SPACING_18,
)


class TabPlaceholderView(ft.Container):
    """Clean placeholder container for tabs implemented in subsequent phases."""

    def __init__(
        self,
        tab_name: str,
        *,
        description: str,
        icon_name: str,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.tab_name = tab_name
        self.description = description
        self.icon_name = icon_name
        palette = get_palette(theme_mode)

        icon_control = get_icon(
            icon_name,
            size=48.0,
            color=palette["muted"],
        )

        title_control = ft.Text(
            value=tab_name,
            size=FONT_SIZE_H1,
            weight=ft.FontWeight.W_700,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
        )

        desc_control = ft.Text(
            value=description,
            size=FONT_SIZE_BODY,
            weight=ft.FontWeight.NORMAL,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
            text_align=ft.TextAlign.CENTER,
        )

        content_column = ft.Column(
            controls=[icon_control, title_control, desc_control],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=SPACING_12,
        )

        super().__init__(
            content=content_column,
            alignment=ft.Alignment(0, 0),
            expand=True,
            bgcolor=palette["background"],
            padding=ft.Padding.all(SPACING_18),
        )


class AppShellHeader(ft.Container):
    """Contextual header bar with tab title and global Add Link action."""

    def __init__(
        self,
        title: str = "Inbox",
        *,
        on_add_link: Callable[[Any], None] | None = None,
        on_theme_toggle: Callable[[Any], None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self._title = title
        self.on_add_link = on_add_link
        self.on_theme_toggle = on_theme_toggle
        self.current_theme_mode = theme_mode

        palette = get_palette(theme_mode)

        self.title_text = ft.Text(
            value=title,
            size=FONT_SIZE_TITLE_LARGE,
            weight=ft.FontWeight.W_700,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
        )

        self.add_button = ft.IconButton(
            icon=ft.Icons.ADD_ROUNDED,
            icon_color=palette["accent"],
            icon_size=24.0,
            tooltip="Add Link / Paste URL",
            width=MIN_TOUCH_TARGET,
            height=MIN_TOUCH_TARGET,
            on_click=on_add_link,
        )

        actions_row = ft.Row(
            controls=[self.add_button],
            spacing=SPACING_8,
            alignment=ft.MainAxisAlignment.END,
        )

        header_row = ft.Row(
            controls=[self.title_text, actions_row],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        super().__init__(
            content=header_row,
            bgcolor=palette["background"],
            padding=ft.Padding.symmetric(horizontal=SPACING_16, vertical=SPACING_8),
            border=ft.Border(bottom=ft.BorderSide(width=1.0, color=palette["line"])),
        )

    def update_title(self, new_title: str) -> None:
        """Update header title label."""
        self._title = new_title
        self.title_text.value = new_title


class AppShellLayout(ft.Column):
    """Persistent mobile shell layout with dynamic header, 4-tab content, and bottom navigation.

    Hard rule: Exactly 4 tabs (Inbox, Folders, Search, Settings).
    Ask is accessed from Search or folder menus; Ask is never a tab.
    """

    def __init__(
        self,
        *,
        inbox_view: ft.Control | None = None,
        folders_view: ft.Control | None = None,
        search_view: ft.Control | None = None,
        settings_view: ft.Control | None = None,
        on_add_link: Callable[[], None] | None = None,
        on_tab_change: Callable[[int], None] | None = None,
        initial_tab: int = TAB_INBOX,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        if not (0 <= initial_tab < TAB_COUNT):
            raise ValueError(f"initial_tab must be between 0 and {TAB_COUNT - 1}, got {initial_tab}")

        self.selected_index = initial_tab
        self.on_add_link = on_add_link
        self.on_tab_change = on_tab_change
        self.current_theme_mode = theme_mode

        palette = get_palette(theme_mode)

        # Header with Add Link action
        self.header = AppShellHeader(
            title=TAB_NAMES[initial_tab],
            on_add_link=lambda _: self.trigger_add_link(),
            theme_mode=theme_mode,
        )

        # Tab views dictionary for state preservation
        self._inbox_view = inbox_view or ft.Container(
            content=ft.Text("Inbox View Placeholder"),
            expand=True,
            bgcolor=palette["background"],
        )
        self._folders_view = folders_view or TabPlaceholderView(
            "Folders",
            description="Organize your saves by topic and hierarchical collections.",
            icon_name="folder",
            theme_mode=theme_mode,
        )
        self._search_view = search_view or TabPlaceholderView(
            "Search",
            description="Search saves and chat with your AI knowledge base.",
            icon_name="search",
            theme_mode=theme_mode,
        )
        self._settings_view = settings_view or TabPlaceholderView(
            "Settings",
            description="Configure AI models, storage, themes, and device preferences.",
            icon_name="settings",
            theme_mode=theme_mode,
        )

        self.tab_views: dict[int, ft.Control] = {
            TAB_INBOX: self._inbox_view,
            TAB_FOLDERS: self._folders_view,
            TAB_SEARCH: self._search_view,
            TAB_SETTINGS: self._settings_view,
        }

        # Content container displaying active tab
        self.content_area = ft.Container(
            content=self.tab_views[self.selected_index],
            expand=True,
            bgcolor=palette["background"],
        )

        # Bottom navigation bar
        self.nav_bar = SharedNavigationBar(
            selected_index=self.selected_index,
            on_tab_change=self.set_tab,
            theme_mode=theme_mode,
        )

        super().__init__(
            controls=[
                self.header,
                self.content_area,
                self.nav_bar,
            ],
            spacing=0,
            expand=True,
        )

    def set_tab(self, index: int) -> None:
        """Switch active tab, update header title, and notify callback."""
        if not (0 <= index < TAB_COUNT):
            raise ValueError(f"Tab index must be between 0 and {TAB_COUNT - 1}, got {index}")

        self.selected_index = index
        self.header.update_title(TAB_NAMES[index])
        self.content_area.content = self.tab_views[index]
        self.nav_bar.selected_index = index

        if self.on_tab_change is not None:
            self.on_tab_change(index)

    def set_inbox_view(self, view: ft.Control) -> None:
        """Inject or update the real Inbox view."""
        self._inbox_view = view
        self.tab_views[TAB_INBOX] = view
        if self.selected_index == TAB_INBOX:
            self.content_area.content = view

    def set_folders_view(self, view: ft.Control) -> None:
        """Inject or update the real Folders view."""
        self._folders_view = view
        self.tab_views[TAB_FOLDERS] = view
        if self.selected_index == TAB_FOLDERS:
            self.content_area.content = view

    def set_search_view(self, view: ft.Control) -> None:
        """Inject or update the real Search view."""
        self._search_view = view
        self.tab_views[TAB_SEARCH] = view
        if self.selected_index == TAB_SEARCH:
            self.content_area.content = view

    def set_settings_view(self, view: ft.Control) -> None:
        """Inject or update the real Settings view."""
        self._settings_view = view
        self.tab_views[TAB_SETTINGS] = view
        if self.selected_index == TAB_SETTINGS:
            self.content_area.content = view

    def trigger_add_link(self) -> None:
        """Trigger the global Add Link callback."""
        if self.on_add_link is not None:
            self.on_add_link()

    def set_theme_mode(self, theme_mode: ft.ThemeMode | str) -> None:
        """Update theme mode across shell and rebuild palette-dependent controls."""
        self.current_theme_mode = theme_mode
        palette = get_palette(theme_mode)
        self.content_area.bgcolor = palette["background"]
        # Update header
        self.header.bgcolor = palette["background"]
        self.header.title_text.color = palette["ink"]
        self.header.add_button.icon_color = palette["accent"]
        self.header.border = ft.Border(bottom=ft.BorderSide(width=1.0, color=palette["line"]))
        # Update nav
        self.nav_bar.bgcolor = palette["background"]
        self.nav_bar.indicator_color = palette["accent_bg"]
        self.nav_bar.border = ft.Border(top=ft.BorderSide(width=1.0, color=palette["line"]))
