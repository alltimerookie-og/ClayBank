"""Recent Saves Carousel for ClayBank.

Presents a horizontal scrolling carousel of recently captured saves with cover
gradients, platform chips, title truncation, and item selection callbacks.

Derived from Docs/Phases.md Phase 2, Docs/api/schemas/save-page.json, and Prototype v2.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlparse
import flet as ft

from app.shell.theme import COVER_GRADIENTS, get_palette
from app.shell.tokens import (
    CARD_RADIUS,
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_LABEL,
    FONT_SIZE_MICRO,
    FONT_SIZE_TITLE,
    SPACING_4,
    SPACING_8,
    SPACING_12,
    SPACING_16,
)
from app.ui.card import ClayCard
from app.ui.chips import PlatformChip

GRADIENT_KEYS: tuple[str, ...] = ("g1", "g2", "g3", "g4")
MAX_RECENT_ITEMS: int = 10


def format_relative_timestamp(iso_str: str | None) -> str:
    """Format ISO-8601 timestamp to friendly relative or short date string."""
    if not iso_str:
        return "Recent"
    try:
        # Standard ISO parse
        cleaned = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        now = datetime.now(timezone.utc)
        diff = now - dt

        seconds = diff.total_seconds()
        if seconds < 60:
            return "Just now"
        if seconds < 3600:
            mins = int(seconds // 60)
            return f"{mins}m ago"
        if seconds < 86400:
            hours = int(seconds // 3600)
            return f"{hours}h ago"
        return dt.strftime("%b %d")
    except Exception:
        return "Recent"


def extract_title_or_domain(item: dict[str, Any]) -> str:
    """Derive display title from item metadata or domain fallback."""
    title = item.get("title") or item.get("user_context")
    if title:
        return str(title).strip()
    url = item.get("url", "")
    if url:
        try:
            parsed = urlparse(url)
            if parsed.netloc:
                return parsed.netloc.replace("www.", "")
        except Exception:
            pass
    return "Saved Link"


class RecentSaveCard(ClayCard):
    """Compact 150x180 card displayed within the horizontal recent carousel."""

    def __init__(
        self,
        item: dict[str, Any],
        *,
        gradient_key: str = "g1",
        on_select: Callable[[dict[str, Any]], None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.item = dict(item)
        self.on_select = on_select
        self.theme_mode_val = theme_mode

        palette = get_palette(theme_mode)

        # Gradient cover block
        grad_tuple = COVER_GRADIENTS.get(gradient_key, COVER_GRADIENTS["g1"])
        self.cover_gradient = ft.Container(
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=[grad_tuple[0], grad_tuple[1]],
            ),
            border_radius=ft.BorderRadius.all(8.0),
            height=60.0,
            alignment=ft.Alignment(0, 0),
            content=ft.Icon(
                icon=ft.Icons.AUTO_STORIES_ROUNDED,
                size=24.0,
                color="rgba(255,255,255,0.75)",
            ),
        )

        # Platform Chip
        platform_name = item.get("platform") or item.get("source_app") or "web"
        self.platform_chip = PlatformChip(
            platform=str(platform_name),
            theme_mode=theme_mode,
        )

        # Truncated Title
        display_title = extract_title_or_domain(item)
        self.title_text = ft.Text(
            value=display_title,
            size=FONT_SIZE_BODY,
            weight=ft.FontWeight.W_600,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        # Relative timestamp
        ts_label = format_relative_timestamp(item.get("captured_at"))
        self.timestamp_text = ft.Text(
            value=ts_label,
            size=FONT_SIZE_MICRO,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
        )

        card_content = ft.Column(
            controls=[
                self.cover_gradient,
                ft.Row(controls=[self.platform_chip], alignment=ft.MainAxisAlignment.START),
                self.title_text,
                self.timestamp_text,
            ],
            spacing=SPACING_4,
            tight=True,
        )

        super().__init__(
            content=card_content,
            width=150.0,
            padding=SPACING_8,
            theme_mode=theme_mode,
            on_click=lambda _: self._handle_click(),
        )

    def _handle_click(self) -> None:
        if self.on_select is not None:
            self.on_select(self.item)


class RecentSavesCarousel(ft.Container):
    """Horizontal scrolling carousel presenting up to 10 recently captured saves."""

    def __init__(
        self,
        saves: list[dict[str, Any]] | None = None,
        *,
        on_select_save: Callable[[dict[str, Any]], None] | None = None,
        is_loading: bool = False,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.on_select_save = on_select_save
        self.theme_mode_val = theme_mode
        self._saves: list[dict[str, Any]] = list(saves or [])
        self._is_loading = is_loading

        self.cards_row = ft.Row(
            controls=[],
            spacing=SPACING_12,
            scroll=ft.ScrollMode.ADAPTIVE,
        )

        palette = get_palette(theme_mode)

        self.empty_label = ft.Text(
            value="No recent saves yet",
            size=FONT_SIZE_LABEL,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
            visible=False,
        )

        self.loading_indicator = ft.ProgressBar(
            width=200.0,
            color=palette["accent"],
            bgcolor=palette["chip"],
            visible=False,
        )

        super().__init__(
            content=ft.Column(
                controls=[
                    self.loading_indicator,
                    self.empty_label,
                    self.cards_row,
                ],
                spacing=SPACING_8,
            ),
            padding=ft.Padding.symmetric(vertical=SPACING_4),
        )

        self._rebuild()

    def set_saves(self, saves: list[dict[str, Any]]) -> None:
        """Update carousel saves list and rebuild cards."""
        self._saves = list(saves)
        self._is_loading = False
        self._rebuild()

    def set_loading(self, loading: bool) -> None:
        """Set loading state."""
        self._is_loading = loading
        self._rebuild()

    def _rebuild(self) -> None:
        """Reconstruct cards based on current state."""
        self.loading_indicator.visible = self._is_loading
        if self._is_loading:
            self.empty_label.visible = False
            self.cards_row.controls = []
            return

        if not self._saves:
            self.empty_label.visible = True
            self.cards_row.controls = []
            return

        self.empty_label.visible = False
        display_items = self._saves[:MAX_RECENT_ITEMS]

        new_controls: list[ft.Control] = []
        for i, item in enumerate(display_items):
            g_key = GRADIENT_KEYS[i % len(GRADIENT_KEYS)]
            card = RecentSaveCard(
                item,
                gradient_key=g_key,
                on_select=self.on_select_save,
                theme_mode=self.theme_mode_val,
            )
            new_controls.append(card)

        self.cards_row.controls = new_controls
