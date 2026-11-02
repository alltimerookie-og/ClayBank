"""Add Link Paste Sheet for ClayBank.

Modal bottom sheet supporting foreground clipboard detection, URL validation,
quick-tag selection, optional user context, and capture submission.

Derived from Docs/Phases.md Phase 2, Docs/api/schemas/save-capture.json, and Prototype v2.
"""

from __future__ import annotations

from urllib.parse import urlparse
from typing import Any, Callable, cast
import flet as ft

from app.shell.icons import get_icon
from app.shell.theme import get_palette
from app.shell.tokens import (
    CARD_RADIUS,
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_LABEL,
    FONT_SIZE_MICRO,
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
)
from app.ui.card import ClaySheet
from app.ui.chips import TagChip

# Standard quick-tags offered at capture time
DEFAULT_QUICK_TAGS: tuple[str, ...] = ("ai", "reading", "recipe", "dev", "video")


def is_valid_url(url: str) -> bool:
    """Validate whether input is a valid HTTP or HTTPS URL."""
    cleaned = url.strip()
    try:
        parsed = urlparse(cleaned)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


class AddLinkPasteSheet(ClaySheet):
    """Bottom sheet modal for capturing links with clipboard auto-detection."""

    def __init__(
        self,
        *,
        on_submit: Callable[[dict[str, Any]], Any] | None = None,
        on_cancel: Callable[[], None] | None = None,
        on_success: Callable[[dict[str, Any]], None] | None = None,
        clipboard_reader: Callable[[], str | None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.on_submit = on_submit
        self.on_cancel = on_cancel
        self.on_success = on_success
        self.clipboard_reader = clipboard_reader
        self.theme_mode_val = theme_mode

        self.is_loading = False
        self.is_duplicate = False
        self.selected_tags: set[str] = set()

        palette = get_palette(theme_mode)

        # Header Title and Close Button
        self.title_text = ft.Text(
            value="Add Link",
            size=FONT_SIZE_TITLE_LARGE,
            weight=ft.FontWeight.W_700,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
        )

        self.close_button = ft.IconButton(
            icon=ft.Icons.CLOSE_ROUNDED,
            icon_color=palette["muted"],
            icon_size=20.0,
            tooltip="Cancel / Close",
            on_click=lambda _: self.cancel(),
        )

        header_row = ft.Row(
            controls=[self.title_text, self.close_button],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Clipboard detection banner
        self.clipboard_banner_text = ft.Text(
            value="Detected link in clipboard",
            size=FONT_SIZE_LABEL,
            weight=ft.FontWeight.W_500,
            color=palette["accent_ink"],
            font_family=FONT_FAMILY_UI,
        )

        self.clipboard_banner = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CONTENT_PASTE_ROUNDED, size=16.0, color=palette["accent"]),
                    self.clipboard_banner_text,
                ],
                spacing=SPACING_8,
            ),
            bgcolor=palette["accent_bg"],
            padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
            border_radius=ft.BorderRadius.all(CARD_RADIUS),
            visible=False,
        )

        # URL Input field
        self.url_field = ft.TextField(
            label="URL",
            hint_text="https://...",
            prefix_icon=ft.Icons.LINK_ROUNDED,
            autofocus=True,
            border_color=palette["line"],
            focused_border_color=palette["accent"],
            text_size=FONT_SIZE_BODY,
            suffix=ft.IconButton(
                icon=ft.Icons.CLEAR_ROUNDED,
                icon_size=18.0,
                icon_color=palette["muted"],
                tooltip="Clear URL",
                on_click=lambda _: self.clear_url(),
            ),
        )

        # User context notes field
        self.context_field = ft.TextField(
            label="Notes / Context (optional)",
            hint_text="e.g. Try this garlic sauce recipe this weekend",
            border_color=palette["line"],
            focused_border_color=palette["accent"],
            text_size=FONT_SIZE_BODY,
            max_lines=2,
        )

        # Destination Folder Indicator (defaults to Inbox)
        self.folder_label = ft.Text(
            value="Destination: Inbox",
            size=FONT_SIZE_LABEL,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
        )

        # Quick tags row
        self.tag_chips: list[TagChip] = []
        for tag in DEFAULT_QUICK_TAGS:
            chip = TagChip(
                tag,
                selected=False,
                on_click=lambda _, t=tag: self.toggle_tag(t),
                theme_mode=theme_mode,
            )
            self.tag_chips.append(chip)

        self.tags_row = ft.Row(
            controls=cast(list[ft.Control], self.tag_chips),
            spacing=SPACING_8,
            wrap=True,
        )

        # Error / Duplicate feedback message
        self.feedback_text = ft.Text(
            value="",
            size=FONT_SIZE_LABEL,
            color=palette["accent"],
            font_family=FONT_FAMILY_UI,
            visible=False,
        )

        # Submit Action Button
        self.submit_button = ft.FilledButton(
            "Capture & Save",
            style=ft.ButtonStyle(
                bgcolor=palette["accent"],
                color=palette["accent_fg"],
                padding=ft.Padding.symmetric(horizontal=SPACING_24, vertical=SPACING_12),
            ),
            on_click=lambda _: self.submit(),
        )

        actions_row = ft.Row(
            controls=[
                self.feedback_text,
                ft.Container(expand=True),
                self.submit_button,
            ],
            alignment=ft.MainAxisAlignment.END,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        sheet_content = ft.Column(
            controls=[
                header_row,
                self.clipboard_banner,
                self.url_field,
                self.context_field,
                self.folder_label,
                ft.Text("Quick Tags", size=FONT_SIZE_LABEL, weight=ft.FontWeight.W_600, color=palette["muted"]),
                self.tags_row,
                ft.Container(height=SPACING_8),
                actions_row,
            ],
            spacing=SPACING_12,
            tight=True,
        )

        super().__init__(
            content=sheet_content,
            padding=SPACING_18,
            theme_mode=theme_mode,
        )

        # Check foreground clipboard on initial load
        self.check_clipboard()

    def check_clipboard(self) -> None:
        """Inspect foreground clipboard for a valid URL and prefill if present."""
        clip_content: str | None = None
        if self.clipboard_reader is not None:
            clip_content = self.clipboard_reader()

        if clip_content and is_valid_url(clip_content):
            self.url_field.value = clip_content.strip()
            self.clipboard_banner.visible = True
            self.clipboard_banner_text.value = f"Prefilled from clipboard: {clip_content.strip()}"

    def clear_url(self) -> None:
        """Clear URL input and reset validation feedback."""
        self.url_field.value = ""
        self.url_field.error = None
        self.feedback_text.visible = False
        self.clipboard_banner.visible = False

    def toggle_tag(self, tag: str) -> None:
        """Toggle quick tag selection."""
        clean = tag.strip().lstrip("#")
        if clean in self.selected_tags:
            self.selected_tags.remove(clean)
        else:
            self.selected_tags.add(clean)

        # Refresh chip styles
        for chip in self.tag_chips:
            c_tag = chip.tag_name.lstrip("#")
            chip.selected = c_tag in self.selected_tags
            palette = get_palette(self.theme_mode_val)
            if chip.selected:
                chip.bgcolor = palette["accent_bg"]
                chip.border = ft.Border.all(width=1.0, color=palette["accent"])
            else:
                chip.bgcolor = palette["chip"]
                chip.border = None

    def cancel(self) -> None:
        """Cancel capture and invoke cancel callback."""
        if self.on_cancel is not None:
            self.on_cancel()

    def submit(self, force: bool = False) -> None:
        """Validate input, build payload, and execute submit callback."""
        url = (self.url_field.value or "").strip()
        if not url:
            self.url_field.error = "URL is required"
            return
        if not is_valid_url(url):
            self.url_field.error = "Please enter a valid HTTP or HTTPS URL"
            return

        self.url_field.error = None
        self.is_loading = True
        self.submit_button.disabled = True
        self.feedback_text.visible = False

        payload: dict[str, Any] = {
            "url": url,
            "source_app": "clipboard" if self.clipboard_banner.visible else "manual_paste",
            "user_context": (self.context_field.value or "").strip(),
            "suggested_folder_id": None,
            "force": force,
        }

        if self.on_submit is not None:
            try:
                res = self.on_submit(payload)
                self.is_loading = False
                self.submit_button.disabled = False

                if isinstance(res, dict) and res.get("error") == "already_saved":
                    self.is_duplicate = True
                    self.feedback_text.value = "Already saved in library"
                    self.feedback_text.visible = True
                    return

                # Success
                if self.on_success is not None:
                    self.on_success(res if isinstance(res, dict) else payload)
            except Exception as ex:
                self.is_loading = False
                self.submit_button.disabled = False
                self.feedback_text.value = str(ex)
                self.feedback_text.visible = True
        else:
            self.is_loading = False
            self.submit_button.disabled = False
            if self.on_success is not None:
                self.on_success(payload)
