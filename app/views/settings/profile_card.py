"""Profile and synchronization status card for ClayBank Settings.

Displays user identity avatar, name, last backup timestamp, and real-time sync status chip.
Derived from Docs/Phases.md Phase 7, Docs/Design.md §8, Docs/UIUX.md §11, and Prototype v2.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_MICRO,
    FONT_SIZE_MUTED,
    FONT_SIZE_TITLE,
    MIN_TOUCH_TARGET,
    PILL_RADIUS,
    SPACING_4,
    SPACING_8,
    SPACING_12,
    SPACING_16,
)
from app.ui.card import ClayCard


def _extract_initials(name: str | None) -> str:
    """Extract 1-2 uppercase initials from a name string."""
    if not name or not name.strip():
        return "LU"
    parts = [p.strip() for p in name.strip().split() if p.strip()]
    if not parts:
        return "LU"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[-1][0]}".upper()


def _format_backup_label(last_backup: str | None) -> str:
    """Format backup timestamp into a clean label."""
    if not last_backup or not last_backup.strip():
        return "No backups yet"

    val = last_backup.strip()
    if val.lower().startswith("last backup:"):
        return val

    # Try ISO parsing
    try:
        clean_iso = val.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_iso)
        # Display clean date/time UTC
        formatted = dt.strftime("%Y-%m-%d %H:%M UTC")
        return f"Last backup: {formatted}"
    except (ValueError, TypeError):
        return f"Last backup: {val}"


class ProfileSyncCard(ClayCard):
    """Profile identity and sync status card adhering to ClayBank tokens."""

    def __init__(
        self,
        *,
        user_name: str | None = None,
        avatar_text: str | None = None,
        avatar_url: str | None = None,
        last_backup: str | None = None,
        sync_status: str = "Synced",
        on_sync_click: Callable[[], None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
        width: float | None = None,
    ) -> None:
        self.theme_mode_val = theme_mode
        self._user_name = user_name
        self._avatar_text = avatar_text or _extract_initials(user_name)
        self._avatar_url = avatar_url
        self._last_backup = last_backup
        self._sync_status = sync_status
        self.on_sync_click = on_sync_click

        palette = get_palette(theme_mode)

        # 1. Avatar (44x44, radius 22)
        avatar_content = ft.Text(
            value=self._avatar_text,
            size=FONT_SIZE_BODY,
            weight=ft.FontWeight.W_700,
            color=palette["accent_ink"],
            font_family=FONT_FAMILY_UI,
        )
        self.avatar = ft.CircleAvatar(
            radius=22.0,
            foreground_image_src=avatar_url if avatar_url else None,
            content=avatar_content if not avatar_url else None,
            bgcolor=palette["accent_bg"],
        )

        # 2. Identity info
        display_name = (user_name or "").strip() or "Local User"
        self.name_text = ft.Text(
            value=display_name,
            size=FONT_SIZE_TITLE,
            weight=ft.FontWeight.W_700,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
            no_wrap=True,
        )

        self.backup_text = ft.Text(
            value=_format_backup_label(last_backup),
            size=FONT_SIZE_MUTED,
            weight=ft.FontWeight.NORMAL,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
            no_wrap=True,
        )

        info_col = ft.Column(
            controls=[self.name_text, self.backup_text],
            spacing=SPACING_4,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.START,
            expand=True,
        )

        # 3. Status chip
        self.status_chip = self._build_status_chip(sync_status)

        # Assembled row
        content_row = ft.Row(
            controls=[
                self.avatar,
                info_col,
                self.status_chip,
            ],
            spacing=SPACING_12,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        super().__init__(
            content=content_row,
            padding=SPACING_12,
            theme_mode=theme_mode,
            width=width,
        )

    def _build_status_chip(self, status: str) -> ft.Container:
        """Construct a styled chip representing the current sync status."""
        palette = get_palette(self.theme_mode_val)
        norm_status = status.strip().lower()

        is_syncing = "syncing" in norm_status
        is_conflict = "conflict" in norm_status
        is_offline = "offline" in norm_status

        # Tone determination
        if is_conflict:
            bg_color = "#FEE2E2" if self.theme_mode_val == ft.ThemeMode.LIGHT else "#450A0A"
            text_color = "#DC2626" if self.theme_mode_val == ft.ThemeMode.LIGHT else "#FCA5A5"
            border_color = "#EF4444"
            icon = ft.Icons.ERROR_OUTLINE_ROUNDED
        elif is_offline:
            bg_color = palette["card"]
            text_color = palette["muted"]
            border_color = palette["line"]
            icon = ft.Icons.WIFI_OFF_ROUNDED
        elif is_syncing:
            bg_color = palette["accent_bg"]
            text_color = palette["accent_ink"]
            border_color = palette["accent"]
            icon = ft.Icons.SYNC_ROUNDED
        else:
            # Synced
            bg_color = palette["accent_bg"]
            text_color = palette["accent_ink"]
            border_color = palette["accent"]
            icon = ft.Icons.CHECK_ROUNDED

        chip_controls: list[ft.Control] = []
        if is_syncing:
            chip_controls.append(
                ft.ProgressRing(
                    width=12.0,
                    height=12.0,
                    stroke_width=2.0,
                    color=text_color,
                )
            )
        else:
            chip_controls.append(
                ft.Icon(
                    icon,
                    size=14.0,
                    color=text_color,
                )
            )

        chip_controls.append(
            ft.Text(
                value=status,
                size=FONT_SIZE_MICRO,
                weight=ft.FontWeight.W_600,
                color=text_color,
                font_family=FONT_FAMILY_UI,
            )
        )

        chip_content = ft.Row(
            controls=chip_controls,
            spacing=SPACING_4,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        )

        def _handle_click(e: Any) -> None:
            # Prevent duplicate clicks while actively syncing
            if is_syncing:
                return
            if self.on_sync_click is not None:
                self.on_sync_click()

        return ft.Container(
            content=chip_content,
            bgcolor=bg_color,
            border=ft.Border.all(width=1.0, color=border_color),
            border_radius=ft.BorderRadius.all(PILL_RADIUS),
            padding=ft.Padding.symmetric(horizontal=SPACING_8, vertical=SPACING_4),
            alignment=ft.Alignment(0, 0),
            height=MIN_TOUCH_TARGET,
            on_click=_handle_click if self.on_sync_click is not None and not is_syncing else None,
            tooltip="Click to sync now" if self.on_sync_click is not None and not is_syncing else status,
        )

    def set_sync_status(self, status: str) -> None:
        """Update the displayed sync status chip."""
        self._sync_status = status
        new_chip = self._build_status_chip(status)
        self.status_chip = new_chip
        # Replace status chip in the row
        row = self.content
        if isinstance(row, ft.Row) and len(row.controls) >= 3:
            row.controls[2] = new_chip

    def set_last_backup(self, timestamp: str | None) -> None:
        """Update last backup label."""
        self._last_backup = timestamp
        self.backup_text.value = _format_backup_label(timestamp)

    def set_user_name(self, name: str | None) -> None:
        """Update user name and avatar initials."""
        self._user_name = name
        self.name_text.value = (name or "").strip() or "Local User"
        self._avatar_text = _extract_initials(name)
        if not self._avatar_url and isinstance(self.avatar.content, ft.Text):
            self.avatar.content.value = self._avatar_text
