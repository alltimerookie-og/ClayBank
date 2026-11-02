"""Hybrid Search View for ClayBank (Phase 6 deliverable P6-02).

Derived from Docs/Phases.md Phase 6, Docs/Design.md §7.5 & §7.6,
Docs/UIUX.md §9, and Prototype v2 Screen 12.
Renders the canonical Tab 2 Search screen featuring:
- Top 'Ask your library' banner card.
- Search input bar with autofocus, submit, and clear mechanics.
- Recent search query chips.
- Facet filter chips (All, YouTube, Instagram, This month).
- Results count label and self-explaining SearchResultCard stream.
- Loading, empty, and error states.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Sequence
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_H1,
    FONT_SIZE_LABEL,
    FONT_SIZE_MICRO,
    FONT_SIZE_MUTED,
    FONT_SIZE_TITLE,
    MIN_TOUCH_TARGET,
    PILL_RADIUS,
    SPACING_4,
    SPACING_6,
    SPACING_8,
    SPACING_12,
    SPACING_16,
    SPACING_24,
    create_text_style,
)
from app.ui.card import ClayCard
from app.views.search.search_result_card import SearchResultCard

DEFAULT_RECENT_QUERIES = [
    "back pain stretches",
    "notion template",
]

FACET_ALL = "All"
FACET_YOUTUBE = "YouTube"
FACET_INSTAGRAM = "Instagram"
FACET_THIS_MONTH = "This month"
FACETS = (FACET_ALL, FACET_YOUTUBE, FACET_INSTAGRAM, FACET_THIS_MONTH)


def filter_results_by_facet(
    results: Sequence[dict[str, Any]],
    facet: str,
) -> list[dict[str, Any]]:
    """Filter search results collection client-side according to active facet."""
    if facet == FACET_ALL or not facet:
        return list(results)

    filtered: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    for item in results:
        save = item.get("save") or {}
        platform = str(save.get("platform") or save.get("source_app") or "").lower()
        url = str(save.get("url") or "").lower()

        if facet == FACET_YOUTUBE:
            if "youtube" in platform or "youtu.be" in url or "youtube.com" in url:
                filtered.append(item)
        elif facet == FACET_INSTAGRAM:
            if "instagram" in platform or "instagr.am" in url or "instagram.com" in url:
                filtered.append(item)
        elif facet == FACET_THIS_MONTH:
            cap_str = save.get("captured_at")
            if cap_str:
                try:
                    dt = datetime.fromisoformat(cap_str.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if (now - dt).days <= 31:
                        filtered.append(item)
                except Exception:
                    filtered.append(item)
            else:
                filtered.append(item)
        else:
            filtered.append(item)

    return filtered


class SearchView(ft.Container):
    """Main Search View component for Tab 2 of ClayBank."""

    def __init__(
        self,
        *,
        initial_query: str = "",
        folder_scope: str | None = None,
        recent_queries: Sequence[str] | None = None,
        on_search: Callable[[str, str | None, str | None], Any] | None = None,
        on_select_save: Callable[[dict[str, Any]], None] | None = None,
        on_jump_target: Callable[[dict[str, Any], str], None] | None = None,
        on_open_ask: Callable[[str | None], None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.query = initial_query
        self.folder_scope = folder_scope
        self.recent_queries = list(recent_queries or DEFAULT_RECENT_QUERIES)
        self.active_facet = FACET_ALL
        self.cursor: str | None = None
        self.is_loading = False
        self.error_message: str | None = None

        self._raw_results: list[dict[str, Any]] = []
        self.on_search_callback = on_search
        self.on_select_save = on_select_save
        self.on_jump_target = on_jump_target
        self.on_open_ask = on_open_ask
        self.theme_mode_val = theme_mode

        palette = get_palette(theme_mode)

        # 1. Ask Banner Card ("Ask your library")
        ask_icon = ft.Icon(
            ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED,
            size=18.0,
            color=palette["accent"],
        )
        ask_title = ft.Text(
            "Ask your library",
            size=FONT_SIZE_BODY,
            weight=ft.FontWeight.W_600,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
        )
        ask_prompt = ft.Text(
            "folder or everything →",
            size=FONT_SIZE_MUTED,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
        )

        ask_banner_content = ft.Row(
            controls=[
                ask_icon,
                ask_title,
                ft.Container(expand=True),
                ask_prompt,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=SPACING_8,
        )

        self.ask_banner = ft.Container(
            content=ask_banner_content,
            padding=ft.Padding.symmetric(horizontal=SPACING_16, vertical=SPACING_12),
            border=ft.Border.all(1.0, palette["accent"]),
            border_radius=ft.BorderRadius.all(12.0),
            bgcolor=palette["accent_bg"],
            on_click=lambda _: self._handle_open_ask(),
        )

        # 2. Search Bar
        self.search_input = ft.TextField(
            value=initial_query,
            hint_text="Search your saves...",
            autofocus=True,
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            border_color=palette["line"],
            focused_border_color=palette["accent"],
            text_style=ft.TextStyle(
                font_family=FONT_FAMILY_UI,
                size=FONT_SIZE_BODY,
                color=palette["ink"],
            ),
            cursor_color=palette["accent"],
            content_padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
            on_submit=lambda e: self.submit_search(self.search_input.value or ""),
            on_change=lambda e: self._handle_query_changed(),
        )

        self.clear_button = ft.IconButton(
            icon=ft.Icons.CLEAR_ROUNDED,
            icon_size=18.0,
            icon_color=palette["muted"],
            tooltip="Clear search",
            visible=bool(initial_query),
            on_click=lambda _: self.clear_search(),
        )

        search_bar_row = ft.Row(
            controls=[
                ft.Container(content=self.search_input, expand=True),
                self.clear_button,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=SPACING_4,
        )

        # 3. Loading bar
        self.loading_bar = ft.ProgressBar(
            color=palette["accent"],
            bgcolor=palette["chip"],
            visible=False,
        )

        # 4. Error Banner
        self.error_text = ft.Text(
            "",
            color=palette["accent"],
            size=FONT_SIZE_MUTED,
            font_family=FONT_FAMILY_UI,
        )
        self.retry_button = ft.TextButton(
            "Retry",
            style=ft.ButtonStyle(color=palette["accent"]),
            on_click=lambda _: self.submit_search(self.query),
        )
        self.error_banner = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=16.0, color=palette["accent"]),
                    self.error_text,
                    ft.Container(expand=True),
                    self.retry_button,
                ],
                spacing=SPACING_8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
            bgcolor=palette["accent_bg"],
            border_radius=ft.BorderRadius.all(8.0),
            visible=False,
        )

        # 5. Recent queries row
        self.recent_column = ft.Column(spacing=SPACING_6, tight=True)
        self._rebuild_recent_chips()

        # 6. Facet Chips row
        self.facet_row = ft.Row(spacing=SPACING_6, wrap=True)
        self._rebuild_facet_chips()

        # 7. Results summary label
        self.results_summary = ft.Text(
            "",
            size=FONT_SIZE_MUTED,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
            visible=False,
        )

        # 8. Results List Column
        self.results_column = ft.Column(spacing=SPACING_8)

        # Main scrollable view
        main_column = ft.Column(
            controls=[
                self.ask_banner,
                search_bar_row,
                self.loading_bar,
                self.error_banner,
                self.recent_column,
                self.facet_row,
                self.results_summary,
                self.results_column,
            ],
            spacing=SPACING_12,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        super().__init__(
            content=main_column,
            padding=ft.Padding.symmetric(horizontal=SPACING_16, vertical=SPACING_12),
            bgcolor=palette["background"],
            expand=True,
            theme_mode=theme_mode if isinstance(theme_mode, ft.ThemeMode) else None,
        )

        if initial_query:
            self.submit_search(initial_query)

    def _handle_open_ask(self) -> None:
        """Route to Ask view scoped to library or folder."""
        if self.on_open_ask:
            self.on_open_ask(self.folder_scope)

    def _handle_query_changed(self) -> None:
        """Update clear button visibility when text changes."""
        val = self.search_input.value or ""
        self.clear_button.visible = bool(val)
        try:
            self.clear_button.update()
        except Exception:
            pass

    def clear_search(self) -> None:
        """Reset search input and return to recent suggestions."""
        self.query = ""
        self.search_input.value = ""
        self.clear_button.visible = False
        self._raw_results = []
        self.error_message = None
        self.error_banner.visible = False
        self.results_summary.visible = False
        self.results_column.controls = []
        self.recent_column.visible = True
        try:
            self.update()
        except Exception:
            pass

    def _rebuild_recent_chips(self) -> None:
        palette = get_palette(self.theme_mode_val)
        if not self.recent_queries:
            self.recent_column.visible = False
            return

        chips: list[ft.Control] = []
        for q in self.recent_queries:
            chip = ft.Container(
                content=ft.Text(
                    q,
                    size=FONT_SIZE_MICRO,
                    color=palette["chip_ink"],
                    font_family=FONT_FAMILY_UI,
                ),
                padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_6),
                border_radius=ft.BorderRadius.all(PILL_RADIUS),
                bgcolor=palette["chip"],
                on_click=lambda _, query=q: self.submit_search(query),
            )
            chips.append(chip)

        self.recent_column.controls = [
            ft.Text(
                "Recent",
                size=FONT_SIZE_LABEL,
                weight=ft.FontWeight.BOLD,
                color=palette["muted"],
                font_family=FONT_FAMILY_UI,
            ),
            ft.Row(controls=chips, spacing=SPACING_6, wrap=True),
        ]
        self.recent_column.visible = not bool(self.query)

    def _rebuild_facet_chips(self) -> None:
        palette = get_palette(self.theme_mode_val)
        chips: list[ft.Control] = []

        for facet in FACETS:
            is_active = self.active_facet == facet
            bg_c = palette["accent_bg"] if is_active else palette["chip"]
            text_c = palette["accent_ink"] if is_active else palette["chip_ink"]
            border = ft.Border.all(1.0, palette["accent"]) if is_active else None

            chip = ft.Container(
                content=ft.Text(
                    facet,
                    size=FONT_SIZE_MICRO,
                    weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.W_500,
                    color=text_c,
                    font_family=FONT_FAMILY_UI,
                ),
                padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_6),
                border_radius=ft.BorderRadius.all(PILL_RADIUS),
                bgcolor=bg_c,
                border=border,
                on_click=lambda _, f=facet: self.set_facet(f),
            )
            chips.append(chip)

        self.facet_row.controls = chips

    def set_facet(self, facet: str) -> None:
        """Switch active facet filter and re-filter visible results."""
        self.active_facet = facet
        self._rebuild_facet_chips()
        self._render_results()
        try:
            self.update()
        except Exception:
            pass

    def submit_search(self, query: str) -> None:
        """Execute search query against injected adapter or fixture fallback."""
        clean_q = query.strip()
        if not clean_q:
            self.clear_search()
            return

        self.query = clean_q
        self.search_input.value = clean_q
        self.clear_button.visible = True

        # Append to recent queries deduplicated
        if clean_q not in self.recent_queries:
            self.recent_queries.insert(0, clean_q)
            self._rebuild_recent_chips()

        self.recent_column.visible = False
        self.is_loading = True
        self.loading_bar.visible = True
        self.error_banner.visible = False
        try:
            self.update()
        except Exception:
            pass

        # Execute search
        try:
            if self.on_search_callback is not None:
                resp = self.on_search_callback(clean_q, self.folder_scope, None)
                if isinstance(resp, dict):
                    self._raw_results = list(resp.get("results") or [])
                    self.cursor = resp.get("cursor")
                elif isinstance(resp, list):
                    self._raw_results = list(resp)
            else:
                self._raw_results = self._load_fixture_results(clean_q)
        except Exception as e:
            self.error_message = str(e)
            self.error_text.value = f"Search failed: {e}"
            self.error_banner.visible = True
            self._raw_results = []
        finally:
            self.is_loading = False
            self.loading_bar.visible = False
            self._render_results()
            try:
                self.update()
            except Exception:
                pass

    def _load_fixture_results(self, query: str) -> list[dict[str, Any]]:
        """Fallback to fixture results when no adapter callback is provided."""
        try:
            p = Path("Docs/api/fixtures/search-page.fixtures.json")
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                valid = data.get("valid")
                if valid and len(valid) > 0:
                    return list(valid[0].get("results") or [])
        except Exception:
            pass

        # Built-in synthetic fallback
        return [
            {
                "save": {
                    "id": "018f4c1a-0000-7de6-9c8e-000000000001",
                    "title": f"Results for {query}",
                    "platform": "instagram",
                    "folder": "Cooking / Pasta",
                    "kind": "video",
                },
                "match_reason": "transcript",
                "fragment": query,
                "jump_target": "0:42",
                "score": 0.95,
            }
        ]

    def _render_results(self) -> None:
        palette = get_palette(self.theme_mode_val)
        filtered = filter_results_by_facet(self._raw_results, self.active_facet)

        if not self.query:
            self.results_summary.visible = False
            self.results_column.controls = []
            return

        if not filtered:
            self.results_summary.visible = False
            empty_text = ft.Text(
                f"No matches found for '{self.query}'",
                style=create_text_style(
                    size=FONT_SIZE_BODY,
                    color=palette["muted"],
                ),
                text_align=ft.TextAlign.CENTER,
            )
            empty_container = ft.Container(
                content=empty_text,
                padding=ft.Padding.symmetric(vertical=SPACING_24),
                alignment=ft.Alignment(0, 0),
            )
            self.results_column.controls = [empty_container]
            return

        count = len(filtered)
        count_label = "1 result" if count == 1 else f"{count} results"
        self.results_summary.value = (
            f"{count_label} · keyword + meaning · every result explains itself"
        )
        self.results_summary.visible = True

        cards: list[ft.Control] = []
        for item in filtered:
            card = SearchResultCard(
                item,
                on_click=self.on_select_save,
                on_jump=self.on_jump_target,
                theme_mode=self.theme_mode_val,
            )
            cards.append(card)

        self.results_column.controls = cards

    def set_results(self, results: Sequence[dict[str, Any]], cursor: str | None = None) -> None:
        """Directly update search results collection."""
        self._raw_results = list(results)
        self.cursor = cursor
        self._render_results()
        try:
            self.update()
        except Exception:
            pass

