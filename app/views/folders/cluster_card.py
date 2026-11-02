"""Cluster Suggestion Card for ClayBank.

Presents AI cluster proposals when ≥3 unfiled saves belong to a similarity cluster
with no assigned folder.
Adheres to Docs/api/schemas/suggestion.json, suggestion-accept.json, and Prototype v2.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Sequence
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    CARD_RADIUS,
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
    SPACING_16,
    create_text_style,
)
from app.ui.card import ClayCard
from app.ui.chips import FolderChip


class ClusterSuggestionCard(ClayCard):
    """Review card for multi-item cluster folder proposals."""

    def __init__(
        self,
        suggestion_data: dict[str, Any],
        *,
        on_accept: Callable[[dict[str, Any]], None] | None = None,
        on_ignore: Callable[[dict[str, Any]], None] | None = None,
        on_choose_folder: Callable[[dict[str, Any]], None] | None = None,
        on_undo: Callable[[dict[str, Any]], None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.suggestion_data = dict(suggestion_data)
        self.cluster_items: list[dict[str, Any]] = list(suggestion_data.get("cluster") or [])
        self.target_path = str(suggestion_data.get("path") or "General")
        self.confidence_val = float(suggestion_data.get("confidence") or 0.0)
        self.is_accepted = bool(suggestion_data.get("accepted", False))
        self.is_dismissed = bool(suggestion_data.get("dismissed_at"))

        self.on_accept = on_accept
        self.on_ignore = on_ignore
        self.on_choose_folder = on_choose_folder
        self.on_undo = on_undo
        self.theme_mode_val = theme_mode

        self.main_container = ft.Column(spacing=SPACING_8, tight=True)
        self._rebuild_content()

        super().__init__(
            content=self.main_container,
            padding=SPACING_12,
            theme_mode=theme_mode,
        )

    def _rebuild_content(self) -> None:
        palette = get_palette(self.theme_mode_val)

        if self.is_accepted:
            count = len(self.cluster_items)
            confirmation_text = ft.Text(
                f"Filed {count} saves to '{self.target_path}'",
                style=create_text_style(
                    size=FONT_SIZE_BODY,
                    weight=ft.FontWeight.W_600,
                    color=palette["ok_ink"],
                ),
            )
            undo_btn = ft.TextButton(
                "Undo",
                style=ft.ButtonStyle(color=palette["accent_ink"]),
                on_click=lambda _: self.undo(),
            )
            row = ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=palette["ok_ink"], size=18.0),
                    confirmation_text,
                    ft.Container(expand=True),
                    undo_btn,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            self.main_container.controls = [row]
            return

        # Header row: Cluster Proposal badge + confidence score
        badge_text = ft.Text(
            "CLUSTER PROPOSAL",
            size=FONT_SIZE_LABEL,
            weight=ft.FontWeight.BOLD,
            color=palette["accent_ink"],
            font_family=FONT_FAMILY_UI,
        )
        badge_container = ft.Container(
            content=badge_text,
            bgcolor=palette["accent_bg"],
            padding=ft.Padding.symmetric(horizontal=SPACING_8, vertical=SPACING_4),
            border_radius=ft.BorderRadius.all(PILL_RADIUS),
        )

        pct = round(self.confidence_val * 100)
        confidence_text = ft.Text(
            f"{pct}% match",
            size=FONT_SIZE_MICRO,
            weight=ft.FontWeight.W_500,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
        )

        header_row = ft.Row(
            controls=[badge_container, confidence_text],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Target Folder suggestion
        folder_chip = FolderChip(
            path=self.target_path,
            prefix="Propose: → ",
            chevron=True,
            on_click=lambda _: self.choose_folder(),
            theme_mode=self.theme_mode_val,
        )

        prompt_text = ft.Text(
            f"File {len(self.cluster_items)} related saves to '{self.target_path}'?",
            style=create_text_style(
                size=FONT_SIZE_BODY,
                weight=ft.FontWeight.W_600,
                color=palette["ink"],
            ),
        )

        # Member items preview list (up to 3 previews)
        preview_controls: list[ft.Control] = []
        for item in self.cluster_items[:3]:
            title = str(item.get("title") or "Save item")
            preview_row = ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INSERT_DRIVE_FILE_OUTLINED, size=14.0, color=palette["muted"]),
                    ft.Text(
                        title,
                        size=FONT_SIZE_MUTED,
                        color=palette["muted"],
                        font_family=FONT_FAMILY_UI,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
                spacing=SPACING_6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            preview_controls.append(preview_row)

        if len(self.cluster_items) > 3:
            remainder = len(self.cluster_items) - 3
            preview_controls.append(
                ft.Text(
                    f"+ {remainder} more saves",
                    size=FONT_SIZE_MICRO,
                    italic=True,
                    color=palette["muted"],
                )
            )

        previews_box = ft.Container(
            content=ft.Column(controls=preview_controls, spacing=SPACING_4, tight=True),
            padding=ft.Padding.only(left=SPACING_8),
        )

        # Action Buttons
        self.ignore_button = ft.IconButton(
            icon=ft.Icons.CLOSE_ROUNDED,
            icon_color=palette["muted"],
            icon_size=20.0,
            tooltip="Ignore proposal",
            width=MIN_TOUCH_TARGET,
            height=MIN_TOUCH_TARGET,
            on_click=lambda _: self.ignore(),
        )

        self.accept_button = ft.IconButton(
            icon=ft.Icons.CHECK_ROUNDED,
            icon_color=palette["ok_ink"],
            bgcolor=palette["ok"],
            icon_size=20.0,
            tooltip=f"File {len(self.cluster_items)} saves to {self.target_path}",
            width=MIN_TOUCH_TARGET,
            height=MIN_TOUCH_TARGET,
            on_click=lambda _: self.accept(),
        )

        actions_row = ft.Row(
            controls=[
                folder_chip,
                ft.Container(expand=True),
                self.ignore_button,
                self.accept_button,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.main_container.controls = [
            header_row,
            prompt_text,
            previews_box,
            actions_row,
        ]

    def accept(self) -> None:
        """Accept cluster suggestion and file member saves."""
        self.is_accepted = True
        self._rebuild_content()
        try:
            self.update()
        except Exception:
            pass

        payload = {
            "type": "cluster",
            "cluster": self.cluster_items,
            "path": self.target_path,
            "confidence": self.confidence_val,
            "accept": True,
        }
        if self.on_accept:
            self.on_accept(payload)

    def ignore(self) -> None:
        """Ignore cluster suggestion and record dismissal."""
        self.is_dismissed = True
        self.visible = False
        try:
            self.update()
        except Exception:
            pass

        payload = {
            "type": "cluster",
            "cluster": self.cluster_items,
            "path": self.target_path,
            "confidence": self.confidence_val,
            "accept": False,
            "dismissed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        if self.on_ignore:
            self.on_ignore(payload)

    def undo(self) -> None:
        """Revert acceptance of cluster suggestion."""
        self.is_accepted = False
        self._rebuild_content()
        try:
            self.update()
        except Exception:
            pass

        payload = {
            "type": "cluster",
            "cluster": self.cluster_items,
            "path": self.target_path,
            "confidence": self.confidence_val,
            "accept": False,
        }
        if self.on_undo:
            self.on_undo(payload)

    def choose_folder(self) -> None:
        """Trigger choose alternate folder flow."""
        if self.on_choose_folder:
            self.on_choose_folder(self.suggestion_data)

