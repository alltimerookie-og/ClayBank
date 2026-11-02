"""Quick-Check Review Card for ClayBank.

Presents AI folder recommendations with one-tap Accept, Ignore, confidence score,
and guaranteed reversible undo integration.

Derived from Docs/Phases.md Phase 2, Docs/api/schemas/suggestion.json, and Prototype v2.
"""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    CARD_RADIUS,
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_LABEL,
    FONT_SIZE_MICRO,
    FONT_SIZE_TITLE,
    MIN_TOUCH_TARGET,
    PILL_RADIUS,
    SPACING_4,
    SPACING_8,
    SPACING_12,
    SPACING_16,
)
from app.ui.card import ClayCard
from app.ui.chips import FolderChip, PlatformChip


class QuickCheckCard(ClayCard):
    """Card offering 1-tap review actions for suggested folder assignments."""

    def __init__(
        self,
        suggestion_data: dict[str, Any],
        *,
        title: str = "",
        platform: str = "",
        on_accept: Callable[[str, str], None] | None = None,
        on_ignore: Callable[[str], None] | None = None,
        on_choose_folder: Callable[[str], None] | None = None,
        on_undo: Callable[[], None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.suggestion_data = dict(suggestion_data)
        self.save_id = str(suggestion_data.get("save_id") or "")
        self.target_path = str(suggestion_data.get("path") or "General")
        self.confidence_val = float(suggestion_data.get("confidence") or 0.0)
        self.suggestion_type = str(suggestion_data.get("type", "single"))

        self.on_accept = on_accept
        self.on_ignore = on_ignore
        self.on_choose_folder = on_choose_folder
        self.on_undo = on_undo
        self.theme_mode_val = theme_mode

        self.is_accepted = bool(suggestion_data.get("accepted", False))
        self.is_ignored = bool(suggestion_data.get("dismissed_at") is not None)

        palette = get_palette(theme_mode)

        # Title display (handles single item or cluster count)
        if self.suggestion_type == "cluster":
            cluster_items = suggestion_data.get("cluster", [])
            display_title = f"{len(cluster_items)} related items to organize"
        else:
            display_title = title or "Unfiled Save"

        self.title_text = ft.Text(
            value=display_title,
            size=FONT_SIZE_TITLE,
            weight=ft.FontWeight.W_600,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
            no_wrap=True,
        )

        # Platform chip
        self.platform_chip = PlatformChip(
            platform=platform or "web",
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

        # Suggested folder chip
        self.folder_chip = FolderChip(
            path=self.target_path,
            prefix="→ ",
            chevron=True,
            on_click=lambda _: self.choose_folder(),
            theme_mode=theme_mode,
        )

        # Confidence percentage label
        pct = int(round(self.confidence_val * 100))
        self.confidence_text = ft.Text(
            value=f"{pct}% match",
            size=FONT_SIZE_MICRO,
            weight=ft.FontWeight.W_500,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
        )

        folder_row = ft.Row(
            controls=[
                self.folder_chip,
                self.confidence_text,
            ],
            spacing=SPACING_8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Action Buttons: Ignore (X) and Accept (Check)
        self.ignore_button = ft.IconButton(
            icon=ft.Icons.CLOSE_ROUNDED,
            icon_color=palette["muted"],
            icon_size=20.0,
            tooltip="Ignore suggestion",
            width=MIN_TOUCH_TARGET,
            height=MIN_TOUCH_TARGET,
            on_click=lambda _: self.ignore(),
        )

        self.accept_button = ft.IconButton(
            icon=ft.Icons.CHECK_ROUNDED,
            icon_color=palette["ok_ink"],
            bgcolor=palette["ok"],
            icon_size=20.0,
            tooltip=f"Move to {self.target_path}",
            width=MIN_TOUCH_TARGET,
            height=MIN_TOUCH_TARGET,
            on_click=lambda _: self.accept(),
        )

        # Status text for accepted/ignored state
        self.status_feedback = ft.Text(
            value="",
            size=FONT_SIZE_LABEL,
            font_family=FONT_FAMILY_UI,
            visible=False,
        )

        actions_row = ft.Row(
            controls=[
                self.status_feedback,
                ft.Container(expand=True),
                self.ignore_button,
                self.accept_button,
            ],
            alignment=ft.MainAxisAlignment.END,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        card_content = ft.Column(
            controls=[
                header_row,
                ft.Container(height=SPACING_4),
                folder_row,
                ft.Container(height=SPACING_8),
                actions_row,
            ],
            spacing=SPACING_4,
        )

        super().__init__(
            content=card_content,
            padding=SPACING_16,
            theme_mode=theme_mode,
        )

    def accept(self) -> None:
        """Accept folder recommendation, trigger callback, and provide feedback."""
        self.is_accepted = True
        self.is_ignored = False
        palette = get_palette(self.theme_mode_val)

        self.status_feedback.value = f"Moved to {self.target_path}"
        self.status_feedback.color = palette["ok_ink"]
        self.status_feedback.visible = True
        self.accept_button.disabled = True
        self.ignore_button.disabled = True

        if self.on_accept is not None:
            self.on_accept(self.save_id, self.target_path)

    def ignore(self) -> None:
        """Ignore folder recommendation without moving save out of inbox."""
        self.is_ignored = True
        self.is_accepted = False
        palette = get_palette(self.theme_mode_val)

        self.status_feedback.value = "Suggestion dismissed"
        self.status_feedback.color = palette["muted"]
        self.status_feedback.visible = True
        self.accept_button.disabled = True
        self.ignore_button.disabled = True

        if self.on_ignore is not None:
            self.on_ignore(self.save_id)

    def undo_action(self) -> None:
        """Revert previous accept or ignore action."""
        self.is_accepted = False
        self.is_ignored = False
        self.status_feedback.visible = False
        self.accept_button.disabled = False
        self.ignore_button.disabled = False

        if self.on_undo is not None:
            self.on_undo()

    def choose_folder(self) -> None:
        """Invoke custom/alternative folder picker callback."""
        if self.on_choose_folder is not None:
            self.on_choose_folder(self.save_id)
