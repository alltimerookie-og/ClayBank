"""Search Result Card component for ClayBank (Phase 6 deliverable P6-01).

Derived from Docs/Phases.md Phase 6, Docs/Design.md §2.3 & §7.5,
Docs/UIUX.md §9, and Prototype v2 Screen 12.
Renders a self-explaining search result card displaying title, platform,
match reason text, highlighted matched fragment, score, and jump targets.
"""

from __future__ import annotations

import hashlib
from typing import Any, Callable
from urllib.parse import urlparse
import flet as ft

from app.shell.theme import COVER_GRADIENTS, get_palette
from app.shell.tokens import (
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
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
    create_text_style,
)
from app.ui.card import ClayCard
from app.ui.chips import CitationChip, FolderChip, PlatformChip

# Match reason formatting dictionary
MATCH_REASON_LABELS: dict[str, str] = {
    "transcript": "Match in transcript",
    "title": "Match in title",
    "body": "Match in body",
    "tag": "Match in tag",
    "folder": "Match in folder",
    "semantic": "Match by meaning",
}


def format_match_reason(reason: str | None) -> str:
    """Format match reason enum into clean human-readable text."""
    if not reason:
        return "Match found"
    return MATCH_REASON_LABELS.get(reason.lower(), f"Match in {reason}")


class SearchResultCard(ClayCard):
    """Self-explaining search match result card."""

    def __init__(
        self,
        result_data: dict[str, Any],
        *,
        on_click: Callable[[dict[str, Any]], None] | None = None,
        on_jump: Callable[[dict[str, Any], str], None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.result_data = dict(result_data)
        self.save_data = dict(result_data.get("save") or {})
        self.save_id = str(self.save_data.get("id") or self.save_data.get("save_id") or "")
        self.match_reason = result_data.get("match_reason")
        self.fragment = result_data.get("fragment")
        self.jump_target = result_data.get("jump_target")
        self.score = result_data.get("score")
        self.on_click_callback = on_click
        self.on_jump_callback = on_jump
        self.theme_mode_val = theme_mode

        palette = get_palette(theme_mode)

        # 1. Resolve Title
        title_val = (
            self.save_data.get("title")
            or self.save_data.get("user_context")
            or self.save_data.get("url")
        )
        if not title_val:
            title_val = "Untitled Save"
        elif "http" in str(title_val):
            try:
                parsed = urlparse(str(title_val))
                title_val = parsed.netloc.replace("www.", "") if parsed.netloc else str(title_val)
            except Exception:
                title_val = str(title_val)

        self.title_text = ft.Text(
            value=str(title_val),
            size=FONT_SIZE_TITLE,
            weight=ft.FontWeight.W_600,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        # 2. Thumbnail with media indicator icon
        kind = self.save_data.get("kind", "video")
        seed = (self.save_id or str(title_val)).encode("utf-8")
        digest = hashlib.sha256(seed).digest()
        g_keys = ("g1", "g2", "g3", "g4")
        g_key = g_keys[digest[0] % len(g_keys)]
        start_c, end_c = COVER_GRADIENTS[g_key]

        media_icon = (
            ft.Icons.PLAY_ARROW_ROUNDED
            if kind == "video"
            else ft.Icons.ARTICLE_ROUNDED
        )
        thumbnail = ft.Container(
            width=44.0,
            height=44.0,
            border_radius=ft.BorderRadius.all(10.0),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1.0, -1.0),
                end=ft.Alignment(1.0, 1.0),
                colors=[start_c, end_c],
            ),
            content=ft.Icon(
                media_icon,
                size=20.0,
                color="#FFFFFF",
            ),
            alignment=ft.Alignment(0, 0),
        )

        # 3. Match Reason & Fragment text (Plain text, not a chip per Docs/Design.md §2.3)
        reason_label = format_match_reason(self.match_reason)
        reason_spans: list[ft.TextSpan] = [
            ft.TextSpan(
                text=reason_label,
                style=create_text_style(
                    size=FONT_SIZE_MUTED,
                    color=palette["muted"],
                    weight=ft.FontWeight.W_500,
                ),
            )
        ]
        if self.fragment:
            reason_spans.append(
                ft.TextSpan(
                    text=" · ",
                    style=create_text_style(size=FONT_SIZE_MUTED, color=palette["muted"]),
                )
            )
            reason_spans.append(
                ft.TextSpan(
                    text=f"“{self.fragment}”",
                    style=create_text_style(
                        size=FONT_SIZE_MUTED,
                        color=palette["accent_ink"],
                        weight=ft.FontWeight.W_600,
                    ),
                )
            )

        match_text = ft.Text(
            spans=reason_spans,
            font_family=FONT_FAMILY_UI,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        # 4. Badges / Metadata Row (Jump Target, Folder, Platform, Score)
        meta_items: list[ft.Control] = []

        if self.jump_target:
            jump_chip = CitationChip(
                label=f"▶ {self.jump_target}",
                target_offset=str(self.jump_target),
                save_id=self.save_id,
                is_jump=True,
                on_click=lambda e: self._handle_jump(),
                theme_mode=theme_mode,
            )
            meta_items.append(jump_chip)

        folder_name = self.save_data.get("folder") or self.save_data.get("folder_path")
        if folder_name:
            folder_chip = FolderChip(
                path=str(folder_name),
                theme_mode=theme_mode,
            )
            meta_items.append(folder_chip)

        platform_val = self.save_data.get("platform") or self.save_data.get("source_app")
        if platform_val:
            meta_items.append(
                PlatformChip(
                    platform=str(platform_val),
                    theme_mode=theme_mode,
                )
            )

        if self.score is not None:
            try:
                score_num = float(self.score)
                score_str = f"{score_num:.2f}"
            except (ValueError, TypeError):
                score_str = str(self.score)

            score_badge = ft.Container(
                content=ft.Text(
                    score_str,
                    size=FONT_SIZE_MICRO,
                    color=palette["muted"],
                    font_family=FONT_FAMILY_UI,
                    weight=ft.FontWeight.W_500,
                ),
                padding=ft.Padding.symmetric(horizontal=SPACING_6, vertical=2.0),
                border_radius=ft.BorderRadius.all(PILL_RADIUS),
                bgcolor=palette["chip"],
            )
            meta_items.append(score_badge)

        meta_row = ft.Row(
            controls=meta_items,
            spacing=SPACING_6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True,
        )

        # Text column
        info_col = ft.Column(
            controls=[
                self.title_text,
                match_text,
                meta_row,
            ],
            spacing=SPACING_4,
            tight=True,
            expand=True,
        )

        card_row = ft.Row(
            controls=[
                thumbnail,
                info_col,
            ],
            spacing=SPACING_12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        super().__init__(
            content=card_row,
            padding=SPACING_12,
            theme_mode=theme_mode,
            on_click=lambda _: self._handle_card_click(),
        )

    def _handle_card_click(self) -> None:
        """Handle tap on search result card."""
        if self.on_click_callback:
            self.on_click_callback(self.save_data)

    def _handle_jump(self) -> None:
        """Handle tap on jump target chip without double triggering card tap."""
        if self.on_jump_callback and self.jump_target:
            self.on_jump_callback(self.save_data, str(self.jump_target))
        elif self.on_click_callback:
            self.on_click_callback(self.save_data)
