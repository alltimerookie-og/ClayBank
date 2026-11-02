"""Folder Card component for ClayBank folders grid view.

Derived from Docs/Design.md §2.3, Docs/UIUX.md §7, and Prototype v2.
Renders a folder thumbnail collage, title, and formatted save count with recency.
Enforces the rule: if save_count <= 0, the count is omitted.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Sequence
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_MUTED,
    SPACING_6,
    SPACING_12,
)
from app.ui.card import ClayCard
from app.views.folders.folder_collage import FolderCoverCollage


def format_folder_recency(updated_at_str: str | None) -> str | None:
    """Format an ISO timestamp into human-readable recency (today, 2d ago, etc.)."""
    if not updated_at_str:
        return None
    try:
        clean_str = updated_at_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - dt
        days = delta.days
        if days <= 0:
            return "today"
        if days == 1:
            return "yesterday"
        if days < 30:
            return f"{days}d ago"
        return dt.strftime("%b %d")
    except Exception:
        return None


def format_folder_subtitle(
    save_count: int | None,
    recency: str | None = None,
    updated_at: str | None = None,
) -> str:
    """Format subtitle string respecting the rule: if save_count <= 0, hide count."""
    effective_recency = recency or format_folder_recency(updated_at)
    count = int(save_count) if save_count is not None else 0

    if count <= 0:
        # Save count is hidden when zero or negative
        return effective_recency or ""

    count_label = "1 save" if count == 1 else f"{count} saves"
    if effective_recency:
        return f"{count_label} · {effective_recency}"
    return count_label


class FolderCard(ClayCard):
    """Reusable folder card with cover collage, title, and count."""

    def __init__(
        self,
        folder_data: dict[str, Any],
        *,
        recency: str | None = None,
        gradients: Sequence[str] | None = None,
        on_click: Callable[[Any], None] | None = None,
        on_long_press: Callable[[Any], None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
        width: float | None = None,
    ) -> None:
        self.folder_data = dict(folder_data)
        self.folder_id = str(folder_data.get("id") or "")
        self.folder_name = str(folder_data.get("name") or "Untitled Folder")
        raw_count = folder_data.get("save_count")
        self.save_count = int(raw_count) if raw_count is not None else 0
        self.updated_at = folder_data.get("updated_at")

        self.subtitle_text = format_folder_subtitle(
            save_count=self.save_count,
            recency=recency,
            updated_at=self.updated_at,
        )

        palette = get_palette(theme_mode)

        self.collage = FolderCoverCollage(
            folder_id=self.folder_id,
            folder_name=self.folder_name,
            gradients=gradients,
            theme_mode=theme_mode,
        )

        self.title_control = ft.Text(
            value=self.folder_name,
            size=FONT_SIZE_BODY,
            weight=ft.FontWeight.W_600,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        card_controls: list[ft.Control] = [self.collage, self.title_control]

        if self.subtitle_text:
            self.subtitle_control: ft.Text | None = ft.Text(
                value=self.subtitle_text,
                size=FONT_SIZE_MUTED,
                color=palette["muted"],
                font_family=FONT_FAMILY_UI,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            )
            card_controls.append(self.subtitle_control)
        else:
            self.subtitle_control = None

        col = ft.Column(
            controls=card_controls,
            spacing=SPACING_6,
            tight=True,
        )

        def _handle_click(e: ft.ControlEvent | Any) -> None:
            if on_click is not None:
                try:
                    on_click(self.folder_data)
                except TypeError:
                    on_click(e)

        def _handle_long_press(e: ft.ControlEvent | Any) -> None:
            if on_long_press is not None:
                try:
                    on_long_press(self.folder_data)
                except TypeError:
                    on_long_press(e)

        super().__init__(
            content=col,
            padding=SPACING_12,
            theme_mode=theme_mode,
            on_click=_handle_click,
            width=width,
        )
        if on_long_press is not None:
            self.on_long_press = _handle_long_press
