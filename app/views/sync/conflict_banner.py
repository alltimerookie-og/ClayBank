"""Stale-write conflict recovery banner for ClayBank.

Appears when the synchronization engine returns a 409 conflict, enabling non-destructive
recovery via Keep Both (<Title> (Local Edit)), confirmed Overwrite Server, or Discard Local.
Derived from Docs/Phases.md Phase 7, Docs/Rules.md §5, Docs/UIUX.md §11, and Prototype v2.
"""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    CARD_RADIUS,
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_MICRO,
    FONT_SIZE_MUTED,
    FONT_SIZE_TITLE,
    MIN_TOUCH_TARGET,
    PILL_RADIUS,
    SPACING_4,
    SPACING_6,
    SPACING_8,
    SPACING_10,
    SPACING_12,
    SPACING_16,
)

CONFLICT_MESSAGE = "Sync Conflict: A newer version of this note exists on the server."


def create_local_edit_title(original_title: str | None) -> str:
    """Generate the canonical Keep Both title '<Title> (Local Edit)'."""
    clean = (original_title or "Untitled Note").strip()
    if clean.endswith("(Local Edit)"):
        return clean
    return f"{clean} (Local Edit)"


class ConflictRecoveryBanner(ft.Container):
    """Inline alert banner presenting non-destructive 409 conflict recovery options."""

    def __init__(
        self,
        save_id: str,
        *,
        note_title: str | None = "Untitled Note",
        local_markdown: str | None = None,
        server_updated_at: str | None = None,
        on_keep_both: Callable[[str, str, str | None], Any] | None = None,
        on_overwrite: Callable[[str, str | None], Any] | None = None,
        on_discard: Callable[[str], Any] | None = None,
        on_dismiss: Callable[[], None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
        width: float | None = None,
    ) -> None:
        self.theme_mode_val = theme_mode
        self.save_id = save_id
        self.note_title = note_title or "Untitled Note"
        self.local_markdown = local_markdown
        self.server_updated_at = server_updated_at

        self.on_keep_both = on_keep_both
        self.on_overwrite = on_overwrite
        self.on_discard = on_discard
        self.on_dismiss = on_dismiss

        self._is_resolving = False
        self._confirming_overwrite = False
        self._error_message: str | None = None

        palette = get_palette(theme_mode)

        # Warning Header: Icon + Title + Message
        self.icon_control = ft.Icon(
            icon=ft.Icons.WARNING_AMBER_ROUNDED,
            size=22.0,
            color="#D97706" if theme_mode == ft.ThemeMode.LIGHT else "#FBBF24",
        )

        self.title_text = ft.Text(
            value=CONFLICT_MESSAGE,
            size=FONT_SIZE_BODY,
            weight=ft.FontWeight.W_700,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
            expand=True,
        )

        header_row = ft.Row(
            controls=[self.icon_control, self.title_text],
            spacing=SPACING_8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Context line: note title & timestamp
        self.info_text = ft.Text(
            value=f"Note: \"{self.note_title}\"" + (f" · Server updated: {server_updated_at}" if server_updated_at else ""),
            size=FONT_SIZE_MUTED,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
        )

        # Error banner if an action fails
        self.error_text = ft.Text(
            value="",
            size=FONT_SIZE_MICRO,
            weight=ft.FontWeight.W_600,
            color="#DC2626",
            font_family=FONT_FAMILY_UI,
            visible=False,
        )

        # Actions Row
        self.keep_both_btn = ft.FilledButton(
            content=ft.Text("Keep Both (Recommended)", size=FONT_SIZE_MICRO, weight=ft.FontWeight.W_600),
            style=ft.ButtonStyle(
                bgcolor=palette["accent"],
                color="#FFFFFF",
            ),
            height=MIN_TOUCH_TARGET,
            on_click=lambda _: self._handle_keep_both(),
        )

        self.overwrite_btn = ft.OutlinedButton(
            content=ft.Text("Overwrite Server", size=FONT_SIZE_MICRO),
            height=MIN_TOUCH_TARGET,
            on_click=lambda _: self._handle_overwrite_click(),
        )

        self.discard_btn = ft.TextButton(
            content=ft.Text("Discard Local", size=FONT_SIZE_MICRO),
            style=ft.ButtonStyle(color=palette["muted"]),
            height=MIN_TOUCH_TARGET,
            on_click=lambda _: self._handle_discard(),
        )

        self.spinner = ft.ProgressRing(
            width=18.0,
            height=18.0,
            stroke_width=2.5,
            color=palette["accent"],
            visible=False,
        )

        self.actions_row = ft.Row(
            controls=[
                self.keep_both_btn,
                self.overwrite_btn,
                self.discard_btn,
                self.spinner,
            ],
            spacing=SPACING_8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True,
        )

        # Inline confirmation for destructive overwrite
        self.confirm_text = ft.Text(
            value="Confirm: Replace server version with your local edit?",
            size=FONT_SIZE_MICRO,
            weight=ft.FontWeight.W_600,
            color="#DC2626",
        )

        self.confirm_yes_btn = ft.FilledButton(
            content=ft.Text("Yes, Overwrite", size=FONT_SIZE_MICRO),
            style=ft.ButtonStyle(
                bgcolor="#DC2626",
                color="#FFFFFF",
            ),
            height=MIN_TOUCH_TARGET,
            on_click=lambda _: self._execute_overwrite(),
        )

        self.confirm_cancel_btn = ft.TextButton(
            content=ft.Text("Cancel", size=FONT_SIZE_MICRO),
            height=MIN_TOUCH_TARGET,
            on_click=lambda _: self._cancel_overwrite(),
        )

        self.confirm_row = ft.Row(
            controls=[
                self.confirm_text,
                self.confirm_yes_btn,
                self.confirm_cancel_btn,
            ],
            spacing=SPACING_8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            visible=False,
            wrap=True,
        )

        container_col = ft.Column(
            controls=[
                header_row,
                self.info_text,
                self.error_text,
                self.actions_row,
                self.confirm_row,
            ],
            spacing=SPACING_8,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        )

        # Warning surface colors
        bg_color = "#FEF3C7" if theme_mode == ft.ThemeMode.LIGHT else "#3E2723"
        border_color = "#F59E0B" if theme_mode == ft.ThemeMode.LIGHT else "#D97706"

        super().__init__(
            content=container_col,
            bgcolor=bg_color,
            border=ft.Border.all(width=1.0, color=border_color),
            border_radius=ft.BorderRadius.all(CARD_RADIUS),
            padding=ft.Padding.all(SPACING_12),
            width=width,
        )

    def _set_resolving(self, resolving: bool) -> None:
        """Toggle active resolving/loading state."""
        self._is_resolving = resolving
        self.spinner.visible = resolving
        self.keep_both_btn.disabled = resolving
        self.overwrite_btn.disabled = resolving
        self.discard_btn.disabled = resolving
        self.confirm_yes_btn.disabled = resolving

    def _handle_keep_both(self) -> None:
        """Handle Keep Both: preserve local edit with (Local Edit) name and accept server original."""
        if self._is_resolving:
            return
        self._set_resolving(True)
        self.error_text.visible = False
        new_title = create_local_edit_title(self.note_title)
        try:
            if self.on_keep_both is not None:
                self.on_keep_both(self.save_id, new_title, self.local_markdown)
            self._set_resolving(False)
            if self.on_dismiss is not None:
                self.on_dismiss()
        except Exception as e:
            self._set_resolving(False)
            self.error_text.value = f"Recovery failed: {e}"
            self.error_text.visible = True

    def _handle_overwrite_click(self) -> None:
        """Show confirmation prompt before destructive overwrite."""
        if self._is_resolving:
            return
        self._confirming_overwrite = True
        self.actions_row.visible = False
        self.confirm_row.visible = True

    def _cancel_overwrite(self) -> None:
        """Cancel overwrite confirmation and return to options."""
        self._confirming_overwrite = False
        self.actions_row.visible = True
        self.confirm_row.visible = False

    def _execute_overwrite(self) -> None:
        """Confirmed overwrite server version with local edit."""
        if self._is_resolving:
            return
        self._set_resolving(True)
        self.error_text.visible = False
        try:
            if self.on_overwrite is not None:
                self.on_overwrite(self.save_id, self.local_markdown)
            self._set_resolving(False)
            if self.on_dismiss is not None:
                self.on_dismiss()
        except Exception as e:
            self._set_resolving(False)
            self._cancel_overwrite()
            self.error_text.value = f"Overwrite failed: {e}"
            self.error_text.visible = True

    def _handle_discard(self) -> None:
        """Discard local edit and revert to server state."""
        if self._is_resolving:
            return
        self._set_resolving(True)
        self.error_text.visible = False
        try:
            if self.on_discard is not None:
                self.on_discard(self.save_id)
            self._set_resolving(False)
            if self.on_dismiss is not None:
                self.on_dismiss()
        except Exception as e:
            self._set_resolving(False)
            self.error_text.value = f"Discard failed: {e}"
            self.error_text.visible = True
