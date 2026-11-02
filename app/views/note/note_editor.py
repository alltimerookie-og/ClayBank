"""Markdown Editor with Local-First Auto-Save UX for ClayBank Item Notes.

Provides an expandable, monospace multiline text editor paired with the QuickInsertToolbar.
Enforces local-first debounced auto-saving (~1000ms pause) and on-exit save flushing.
Displays live persistence feedback ('Saved on device ✓', 'Saving...', etc.).

Derived from Docs/Memory.md line 49, Docs/UIUX.md §6, and Docs/api/schemas/note-put.json.
"""

from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Any, Callable
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    FONT_FAMILY_MONO,
    FONT_SIZE_BODY,
    FONT_SIZE_LABEL,
    FONT_SIZE_MICRO,
    SPACING_4,
    SPACING_8,
    SPACING_12,
    create_text_style,
)
from app.views.note.editor_toolbar import QuickInsertToolbar, apply_markdown_syntax

DEBOUNCE_INTERVAL_SEC: float = 1.0


class MarkdownNoteEditor(ft.Container):
    """Full-screen monospace Markdown editor with syntax toolbar and auto-save indicator."""

    def __init__(
        self,
        *,
        save_id: str,
        initial_markdown: str,
        on_save_note: Callable[[str, str, str], Any] | None = None,
        debounce_interval: float = DEBOUNCE_INTERVAL_SEC,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.save_id = save_id
        self.current_markdown = initial_markdown
        self.on_save_note = on_save_note
        self.debounce_interval = debounce_interval
        self.theme_mode_val = theme_mode

        self.is_dirty = False
        self.save_status: str = "Saved on device ✓"
        self._debounce_timer: threading.Timer | None = None
        self._lock = threading.Lock()

        # Selection state tracking for toolbar insertion
        self.cursor_start: int = len(initial_markdown)
        self.cursor_end: int = len(initial_markdown)

        palette = get_palette(theme_mode)

        # Quick syntax toolbar
        self.toolbar = QuickInsertToolbar(
            on_insert=self.handle_toolbar_action,
            theme_mode=theme_mode,
        )

        # Status feedback label
        self.status_text = ft.Text(
            value=self.save_status,
            style=create_text_style(
                size=FONT_SIZE_MICRO,
                color=palette["muted"],
            ),
        )

        # Multiline Monospace TextField
        self.text_field = ft.TextField(
            value=initial_markdown,
            multiline=True,
            min_lines=16,
            expand=True,
            text_style=create_text_style(
                size=FONT_SIZE_BODY,
                is_mono=True,
                color=palette["ink"],
            ),
            bgcolor=palette["background"],
            border_color=palette["line"],
            focused_border_color=palette["accent"],
            cursor_color=palette["accent"],
            content_padding=ft.Padding.all(SPACING_12),
            on_change=self._handle_text_changed,
        )

        top_bar = ft.Row(
            controls=[
                self.toolbar,
                ft.Container(expand=True),
                self.status_text,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        editor_column = ft.Column(
            controls=[
                top_bar,
                ft.Container(height=SPACING_4),
                self.text_field,
            ],
            expand=True,
            spacing=0,
        )

        super().__init__(
            content=editor_column,
            expand=True,
            padding=ft.Padding.symmetric(vertical=SPACING_8),
        )

    def _handle_text_changed(self, e: Any) -> None:
        """Triggered when user types in the editor."""
        new_val = str(self.text_field.value or "")
        self.current_markdown = new_val
        self.cursor_start = len(new_val)
        self.cursor_end = len(new_val)
        self.is_dirty = True

        self._set_status("Saving…")
        self._schedule_debounce()

    def handle_toolbar_action(self, action: str) -> None:
        """Apply toolbar syntax insertion at current cursor position."""
        curr_text = str(self.text_field.value or "")
        new_text, new_start, new_end = apply_markdown_syntax(
            curr_text,
            action,
            self.cursor_start,
            self.cursor_end,
        )
        self.text_field.value = new_text
        self.current_markdown = new_text
        self.cursor_start = new_start
        self.cursor_end = new_end
        self.is_dirty = True

        self._set_status("Saving…")
        self._schedule_debounce()

    def _schedule_debounce(self) -> None:
        """Cancel existing debounce timer and start a new one."""
        with self._lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()

            self._debounce_timer = threading.Timer(
                self.debounce_interval,
                self._execute_auto_save,
            )
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def _execute_auto_save(self) -> None:
        """Execute persistence callback on pause."""
        if not self.is_dirty:
            return

        now_utc = datetime.now(timezone.utc).isoformat()
        content = self.current_markdown

        if self.on_save_note is not None:
            try:
                res = self.on_save_note(self.save_id, content, now_utc)
                self.is_dirty = False
                if isinstance(res, dict) and res.get("offline"):
                    self._set_status("Saved on device ✓ (offline)")
                else:
                    self._set_status("Saved on device ✓")
            except Exception as ex:
                self._set_status(f"Save failed: {ex}")
        else:
            self.is_dirty = False
            self._set_status("Saved on device ✓")

    def flush_pending_save(self) -> None:
        """Synchronously flush any pending debounced save upon exit or unmount."""
        with self._lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
                self._debounce_timer = None

        if self.is_dirty:
            self._execute_auto_save()

    def _set_status(self, text: str) -> None:
        """Safely update status text."""
        self.save_status = text
        self.status_text.value = text

    def set_content(self, markdown: str) -> None:
        """Update editor content programmatically."""
        self.flush_pending_save()
        self.current_markdown = markdown
        self.text_field.value = markdown
        self.is_dirty = False
        self._set_status("Saved on device ✓")
