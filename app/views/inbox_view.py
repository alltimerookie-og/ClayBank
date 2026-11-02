"""Inbox View Shell for ClayBank.

The core operational view integrating the Processing pipeline, Quick-Check review queue,
Recently Added carousel, and vertical unfiled saves stream with pull-to-refresh mechanics.

Derived from Docs/Phases.md Phase 2, Docs/UIUX.md §4.3, and Prototype v2.
"""

from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlparse
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    CARD_RADIUS,
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_H1,
    FONT_SIZE_LABEL,
    FONT_SIZE_MICRO,
    FONT_SIZE_MUTED,
    FONT_SIZE_TITLE,
    FONT_SIZE_TITLE_LARGE,
    MIN_TOUCH_TARGET,
    PILL_RADIUS,
    SPACING_4,
    SPACING_8,
    SPACING_12,
    SPACING_16,
    SPACING_18,
    SPACING_24,
    SPACING_32,
)
from app.ui.card import ClayCard
from app.ui.chips import PlatformChip
from app.views.processing_card import ProcessingCard
from app.views.quick_check_card import QuickCheckCard
from app.views.recent_carousel import RecentSavesCarousel, format_relative_timestamp


class UnfiledSaveItem(ClayCard):
    """Full-width card for an unfiled save displayed in the inbox stream."""

    def __init__(
        self,
        item: dict[str, Any],
        *,
        on_click: Callable[[dict[str, Any]], None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.item = dict(item)
        self.on_click_callback = on_click
        self.theme_mode_val = theme_mode

        palette = get_palette(theme_mode)

        # Title or URL domain
        title_val = item.get("title") or item.get("user_context")
        if not title_val:
            url = item.get("url", "")
            try:
                parsed = urlparse(url)
                title_val = parsed.netloc.replace("www.", "") if parsed.netloc else url
            except Exception:
                title_val = url or "Unfiled Save"

        self.title_text = ft.Text(
            value=str(title_val),
            size=FONT_SIZE_TITLE,
            weight=ft.FontWeight.W_600,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
            no_wrap=True,
        )

        # Platform chip
        platform_name = item.get("platform") or item.get("source_app") or "web"
        self.platform_chip = PlatformChip(
            platform=str(platform_name),
            theme_mode=theme_mode,
        )

        header_row = ft.Row(
            controls=[
                self.title_text,
                ft.Container(expand=True),
                self.platform_chip,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Snippet or note summary
        summary_val = item.get("snippet") or item.get("user_context") or item.get("url") or ""
        self.summary_text = ft.Text(
            value=str(summary_val),
            size=FONT_SIZE_BODY,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        # Relative timestamp
        ts_label = format_relative_timestamp(item.get("captured_at"))
        self.time_text = ft.Text(
            value=ts_label,
            size=FONT_SIZE_MICRO,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
        )

        # Degraded kind badge if unknown
        kind_val = item.get("kind", "web")
        is_unknown = kind_val == "unknown"
        self.degraded_badge = ft.Container(
            content=ft.Text(
                "Degraded / Unknown",
                size=10.0,
                color=palette["muted"],
                font_family=FONT_FAMILY_UI,
            ),
            bgcolor=palette["chip"],
            padding=ft.Padding.symmetric(horizontal=SPACING_8, vertical=2.0),
            border_radius=ft.BorderRadius.all(PILL_RADIUS),
            visible=is_unknown,
        )

        footer_row = ft.Row(
            controls=[
                self.time_text,
                ft.Container(expand=True),
                self.degraded_badge,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        card_content = ft.Column(
            controls=[
                header_row,
                self.summary_text,
                footer_row,
            ],
            spacing=SPACING_8,
        )

        super().__init__(
            content=card_content,
            padding=SPACING_12,
            theme_mode=theme_mode,
            on_click=lambda _: self._handle_click(),
        )

    def _handle_click(self) -> None:
        if self.on_click_callback is not None:
            self.on_click_callback(self.item)


class InboxView(ft.Container):
    """Complete Inbox tab view integrating processing, review queue, and unfiled stream."""

    def __init__(
        self,
        *,
        saves: list[dict[str, Any]] | None = None,
        suggestions: list[dict[str, Any]] | None = None,
        active_jobs: list[dict[str, Any]] | None = None,
        on_add_link: Callable[[], None] | None = None,
        on_refresh: Callable[[], None] | None = None,
        on_select_save: Callable[[dict[str, Any]], None] | None = None,
        on_accept_suggestion: Callable[[str, str], None] | None = None,
        on_ignore_suggestion: Callable[[str], None] | None = None,
        is_loading: bool = False,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self._saves = list(saves or [])
        self._suggestions = list(suggestions or [])
        self._active_jobs = list(active_jobs or [])

        self.on_add_link = on_add_link
        self.on_refresh = on_refresh
        self.on_select_save = on_select_save
        self.on_accept_suggestion = on_accept_suggestion
        self.on_ignore_suggestion = on_ignore_suggestion
        self.theme_mode_val = theme_mode
        self._is_loading = is_loading
        self.error_message: str | None = None

        palette = get_palette(theme_mode)

        # Header with Title and Refresh control
        self.header_title = ft.Text(
            value="Inbox",
            size=FONT_SIZE_H1,
            weight=ft.FontWeight.W_700,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
        )

        self.refresh_button = ft.IconButton(
            icon=ft.Icons.REFRESH_ROUNDED,
            icon_color=palette["muted"],
            icon_size=22.0,
            tooltip="Refresh Inbox",
            on_click=lambda _: self.refresh(),
        )

        header_bar = ft.Row(
            controls=[
                self.header_title,
                ft.Container(expand=True),
                self.refresh_button,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Section containers
        self.processing_column = ft.Column(spacing=SPACING_8)
        self.suggestions_column = ft.Column(spacing=SPACING_8)
        self.recent_carousel = RecentSavesCarousel(
            saves=self._saves,
            on_select_save=self.on_select_save,
            theme_mode=theme_mode,
        )
        self.stream_column = ft.Column(spacing=SPACING_8)

        # Loading Indicator
        self.loading_indicator = ft.ProgressBar(
            color=palette["accent"],
            bgcolor=palette["chip"],
            visible=is_loading,
        )

        # Error Banner
        self.error_banner_text = ft.Text(
            value="",
            size=FONT_SIZE_LABEL,
            color=palette["accent"],
            font_family=FONT_FAMILY_UI,
        )
        self.error_banner = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=16.0, color=palette["accent"]),
                    self.error_banner_text,
                ],
                spacing=SPACING_8,
            ),
            bgcolor=palette["accent_bg"],
            padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
            border_radius=ft.BorderRadius.all(CARD_RADIUS),
            visible=False,
        )

        # Empty State Container
        self.empty_state_icon = ft.Icon(
            icon=ft.Icons.INBOX_ROUNDED,
            size=64.0,
            color=palette["muted"],
        )

        self.empty_state_title = ft.Text(
            value="Your inbox is clear",
            size=FONT_SIZE_TITLE_LARGE,
            weight=ft.FontWeight.W_700,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
            text_align=ft.TextAlign.CENTER,
        )

        self.empty_state_desc = ft.Text(
            value="Capture web pages, reels, and notes to see them organized here.",
            size=FONT_SIZE_BODY,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
            text_align=ft.TextAlign.CENTER,
        )

        self.empty_state_button = ft.FilledButton(
            "Paste a link",
            style=ft.ButtonStyle(
                bgcolor=palette["accent"],
                color=palette["accent_fg"],
                padding=ft.Padding.symmetric(horizontal=SPACING_24, vertical=SPACING_12),
            ),
            on_click=lambda _: self.trigger_add_link(),
        )

        self.empty_state_container = ft.Container(
            content=ft.Column(
                controls=[
                    self.empty_state_icon,
                    self.empty_state_title,
                    self.empty_state_desc,
                    ft.Container(height=SPACING_8),
                    self.empty_state_button,
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=SPACING_8,
            ),
            padding=ft.Padding.all(SPACING_32),
            alignment=ft.Alignment(0, 0),
            visible=False,
        )

        # Main scrollable view
        self.main_list = ft.ListView(
            controls=[
                header_bar,
                self.loading_indicator,
                self.error_banner,
                self.empty_state_container,
                self.processing_column,
                self.suggestions_column,
                self.recent_carousel,
                self.stream_column,
            ],
            spacing=SPACING_16,
            expand=True,
        )

        super().__init__(
            content=self.main_list,
            padding=ft.Padding.symmetric(horizontal=SPACING_16, vertical=SPACING_12),
            expand=True,
            bgcolor=palette["background"],
        )

        self.rebuild_view()

    def set_data(
        self,
        *,
        saves: list[dict[str, Any]] | None = None,
        suggestions: list[dict[str, Any]] | None = None,
        active_jobs: list[dict[str, Any]] | None = None,
    ) -> None:
        """Update data collections and re-render sections."""
        if saves is not None:
            self._saves = list(saves)
        if suggestions is not None:
            self._suggestions = list(suggestions)
        if active_jobs is not None:
            self._active_jobs = list(active_jobs)

        self._is_loading = False
        self.error_message = None
        self.rebuild_view()

    def set_loading(self, loading: bool) -> None:
        """Update loading state."""
        self._is_loading = loading
        self.loading_indicator.visible = loading

    def set_error(self, message: str | None) -> None:
        """Display error banner."""
        self.error_message = message
        if message:
            self.error_banner_text.value = message
            self.error_banner.visible = True
        else:
            self.error_banner.visible = False

    def rebuild_view(self) -> None:
        """Reconstruct UI controls across all four tiers."""
        palette = get_palette(self.theme_mode_val)
        self.loading_indicator.visible = self._is_loading

        if self.error_message:
            self.error_banner_text.value = self.error_message
            self.error_banner.visible = True
        else:
            self.error_banner.visible = False

        has_processing = len(self._active_jobs) > 0
        has_suggestions = len(self._suggestions) > 0
        has_saves = len(self._saves) > 0

        # Empty state check
        is_completely_empty = not (has_processing or has_suggestions or has_saves)
        self.empty_state_container.visible = is_completely_empty

        if is_completely_empty:
            self.processing_column.controls = []
            self.suggestions_column.controls = []
            self.recent_carousel.visible = False
            self.stream_column.controls = []
            return

        # 1. Processing section
        if has_processing:
            proc_cards: list[ft.Control] = [
                ft.Text("Processing", size=FONT_SIZE_LABEL, weight=ft.FontWeight.W_700, color=palette["muted"]),
            ]
            for job in self._active_jobs:
                p_card = ProcessingCard(
                    job,
                    url=job.get("url", ""),
                    kind=job.get("kind", "web"),
                    theme_mode=self.theme_mode_val,
                )
                proc_cards.append(p_card)
            self.processing_column.controls = proc_cards
            self.processing_column.visible = True
        else:
            self.processing_column.controls = []
            self.processing_column.visible = False

        # 2. Quick-Check Review Queue section
        if has_suggestions:
            sugg_controls: list[ft.Control] = [
                ft.Text("Quick Check", size=FONT_SIZE_LABEL, weight=ft.FontWeight.W_700, color=palette["muted"]),
            ]
            for sugg in self._suggestions:
                q_card = QuickCheckCard(
                    sugg,
                    title=sugg.get("title", ""),
                    platform=sugg.get("platform", "web"),
                    on_accept=self.on_accept_suggestion,
                    on_ignore=self.on_ignore_suggestion,
                    theme_mode=self.theme_mode_val,
                )
                sugg_controls.append(q_card)
            self.suggestions_column.controls = sugg_controls
            self.suggestions_column.visible = True
        else:
            self.suggestions_column.controls = []
            self.suggestions_column.visible = False

        # 3. Recently Added Carousel
        if has_saves:
            self.recent_carousel.set_saves(self._saves)
            self.recent_carousel.visible = True
        else:
            self.recent_carousel.visible = False

        # 4. Vertical Unfiled Stream
        if has_saves:
            stream_controls: list[ft.Control] = [
                ft.Text("Unfiled Saves", size=FONT_SIZE_LABEL, weight=ft.FontWeight.W_700, color=palette["muted"]),
            ]
            for item in self._saves:
                stream_card = UnfiledSaveItem(
                    item,
                    on_click=self.on_select_save,
                    theme_mode=self.theme_mode_val,
                )
                stream_controls.append(stream_card)
            self.stream_column.controls = stream_controls
            self.stream_column.visible = True
        else:
            self.stream_column.controls = []
            self.stream_column.visible = False

    def trigger_add_link(self) -> None:
        """Trigger Add Link action."""
        if self.on_add_link is not None:
            self.on_add_link()

    def refresh(self) -> None:
        """Trigger manual refresh callback."""
        if self.on_refresh is not None:
            self.on_refresh()
