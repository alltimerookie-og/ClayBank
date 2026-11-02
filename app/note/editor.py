"""Interactive Note Editor & Viewer modal dialog (ADR 0005, Docs/UIUX.md §6).

Renders stable properties grid, Markdown preview with GFM support,
and in-place monospace Markdown editor with quick-insert formatting chips.
Enforces optimistic concurrency control (HTTP 409 Conflict) and atomic write-through.
"""
from __future__ import annotations

import re
from typing import Any
import flet as ft

from app.shell.components import banner, kind_chip, platform_chip, processing_chip
from app.shell.theme import Tokens as T

_FRONTMATTER_STRIP = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)


def strip_frontmatter(markdown: str) -> str:
    """Strip YAML frontmatter block for clean Markdown body preview."""
    if not markdown:
        return ""
    return _FRONTMATTER_STRIP.sub("", markdown).strip()


class NoteEditorModal:
    """Modal dialog combining Properties Grid, Markdown Preview, and Monospace Editor."""

    def __init__(self, page: ft.Page, state: Any, save: dict, on_closed=None) -> None:
        self.page = page
        self.state = state
        self.save = dict(save)
        self.on_closed = on_closed

        self.note: dict[str, Any] = {}
        self.job: dict[str, Any] = {}
        self.is_editing = False
        self.is_loading = True
        self.is_saving = False
        self.banner_error: str | None = None
        self.banner_warn: str | None = None
        self.server_updated_at: str = ""

        # UI Controls
        self.title_text = ft.Text(
            self.save.get("title") or self.save.get("url") or "Note",
            size=16,
            weight=ft.FontWeight.BOLD,
            color=T.INK,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
            expand=True,
        )

        self.edit_field = ft.TextField(
            multiline=True,
            min_lines=16,
            max_lines=28,
            expand=True,
            text_style=ft.TextStyle(font_family="monospace", size=13),
            border_color=T.LINE,
            focused_border_color=T.ACCENT,
            cursor_color=T.ACCENT,
        )

        self.preview_markdown = ft.Markdown(
            value="",
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
            code_theme="atom-one-light",
            on_tap_link=self._on_tap_link,
            shrink_wrap=True,
        )

        self.properties_grid = ft.Column(spacing=4, tight=True)
        self.body_scroll_container = ft.Column(spacing=10, expand=True, scroll=ft.ScrollMode.AUTO)

        # Actions & Buttons
        self.edit_toggle_btn = ft.TextButton("Edit", icon=ft.Icons.EDIT_OUTLINED, on_click=self._toggle_mode)
        self.save_btn = ft.FilledButton("Save", on_click=self._save_note, style=ft.ButtonStyle(bgcolor=T.ACCENT), visible=False)
        self.close_btn = ft.TextButton("Close", on_click=self.close)
        self.open_url_btn = ft.IconButton(
            icon=ft.Icons.OPEN_IN_NEW,
            tooltip="Open original URL",
            on_click=lambda e: self._open_external_url(),
        )
        self.reprocess_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            tooltip="Reprocess save",
            on_click=lambda e: self.page.run_task(self._reprocess_save),
        )

        self.toolbar_chips = ft.Row(
            controls=[
                ft.Chip(label=ft.Text("H2"), on_click=lambda e: self._insert_text("\n## ")),
                ft.Chip(label=ft.Text("H3"), on_click=lambda e: self._insert_text("\n### ")),
                ft.Chip(label=ft.Text("Bold"), on_click=lambda e: self._insert_text("**bold**")),
                ft.Chip(label=ft.Text("List"), on_click=lambda e: self._insert_text("\n- ")),
                ft.Chip(label=ft.Text("Task"), on_click=lambda e: self._insert_text("\n- [ ] ")),
                ft.Chip(label=ft.Text("Link"), on_click=lambda e: self._insert_text("[text](https://)")),
            ],
            spacing=6,
            visible=False,
            wrap=True,
        )

        self.dialog = ft.AlertDialog(
            title=ft.Row([
                self.title_text,
                self.reprocess_btn,
                self.open_url_btn,
                self.edit_toggle_btn,
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            content=ft.Container(
                content=self.body_scroll_container,
                width=640,
                height=520,
            ),
            actions=[self.save_btn, self.close_btn],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def show(self) -> None:
        """Display the modal dialog and initiate async save load."""
        self._paint_loading()
        self.page.show_dialog(self.dialog)
        self.page.run_task(self._load_save)

    def close(self, _e=None) -> None:
        """Dismiss the modal dialog."""
        try:
            self.page.pop_dialog()
        except Exception:
            self.dialog.open = False
            self.page.update()
        if self.on_closed:
            self.on_closed()

    async def _load_save(self) -> None:
        """Fetch save details including note, frontmatter, and job state."""
        self.is_loading = True
        self.banner_error = None
        self.banner_warn = None
        self.page.update()

        try:
            res = await self.state.client.read_save(self.save["id"])
        except Exception as exc:
            self.banner_error = f"Network error loading note: {type(exc).__name__}"
            self.is_loading = False
            self._paint()
            return

        if not res.ok:
            if res.status == 0:
                self.banner_warn = "Offline — showing cached capture information."
            else:
                self.banner_error = f"Failed to load save: {res.error.message if res.error else 'Error'}"
            self.is_loading = False
            self._paint()
            return

        data = res.data if isinstance(res.data, dict) else {}
        self.save = data.get("save") or self.save
        self.note = data.get("note") or {}
        self.job = data.get("job") or {}
        self.server_updated_at = self.note.get("updated_at") or self.save.get("updated_at") or ""
        self.edit_field.value = self.note.get("markdown") or ""

        self.is_loading = False
        self._paint()

    def _paint_loading(self) -> None:
        self.body_scroll_container.controls.clear()
        self.body_scroll_container.controls.append(ft.ProgressBar(color=T.ACCENT))
        self.body_scroll_container.controls.append(ft.Text("Loading note content…", size=13, color=T.MUTED))
        self.page.update()

    def _paint(self) -> None:
        self.body_scroll_container.controls.clear()

        # Update title text
        title_val = self.save.get("title") or self.save.get("url") or "Note"
        self.title_text.value = title_val

        # 1. Error / Warning Banners
        if self.banner_error:
            self.body_scroll_container.controls.append(banner(self.banner_error, "warn"))
        if self.banner_warn:
            self.body_scroll_container.controls.append(banner(self.banner_warn, "info"))

        # Job errors
        if self.job.get("error"):
            self.body_scroll_container.controls.append(banner(f"Job warning: {self.job['error']}", "warn"))

        # 2. Properties Grid (stable facts only)
        fm = self.note.get("frontmatter") or {}
        self.properties_grid.controls.clear()

        props_items: list[ft.Control] = [
            ft.Row([
                platform_chip(str(self.save.get("platform") or fm.get("source") or "web")),
                kind_chip(str(self.save.get("kind") or "unknown")),
                processing_chip(self.job.get("state")),
            ], spacing=6, wrap=True),
        ]

        # Metadata rows
        meta_details: list[str] = []
        if fm.get("channel"):
            meta_details.append(f"Channel: {fm['channel']}")
        if fm.get("duration"):
            mins, secs = divmod(int(fm["duration"]), 60)
            meta_details.append(f"Duration: {mins}:{secs:02d}")
        if fm.get("folder"):
            meta_details.append(f"Folder: {fm['folder']}")
        if fm.get("saved"):
            meta_details.append(f"Saved: {fm['saved']}")

        if meta_details:
            props_items.append(ft.Text(" · ".join(meta_details), size=12, color=T.MUTED))

        # Tags chips
        tags = fm.get("tags") or []
        if tags:
            tag_chips = [
                ft.Container(
                    content=ft.Text(f"#{t}", size=11, color=T.CHIP_INK),
                    bgcolor=T.CHIP,
                    border_radius=8,
                    padding=ft.Padding(6, 2, 6, 2),
                )
                for t in tags
            ]
            props_items.append(ft.Row(tag_chips, spacing=4, wrap=True))

        self.properties_grid.controls = props_items
        self.body_scroll_container.controls.append(
            ft.Container(
                content=self.properties_grid,
                bgcolor=T.PAGE,
                border_radius=12,
                padding=10,
            )
        )

        # 3. Main Content Area: Edit Mode vs. Preview Mode
        if self.is_editing:
            self.edit_toggle_btn.text = "Preview"
            self.edit_toggle_btn.icon = ft.Icons.VISIBILITY_OUTLINED
            self.save_btn.visible = True
            self.toolbar_chips.visible = True

            self.body_scroll_container.controls.append(self.toolbar_chips)
            self.body_scroll_container.controls.append(self.edit_field)
        else:
            self.edit_toggle_btn.text = "Edit"
            self.edit_toggle_btn.icon = ft.Icons.EDIT_OUTLINED
            self.save_btn.visible = False
            self.toolbar_chips.visible = False

            raw_md = self.note.get("markdown") or ""
            body_md = strip_frontmatter(raw_md)

            if not body_md or body_md == "---\n---":
                self.preview_markdown.value = "_No content generated yet._"
            else:
                self.preview_markdown.value = body_md

            self.body_scroll_container.controls.append(
                ft.Container(
                    content=self.preview_markdown,
                    padding=ft.Padding(4, 8, 4, 8),
                )
            )

        self.page.update()

    def _toggle_mode(self, _e=None) -> None:
        """Toggle between View/Preview mode and Monospace Edit mode."""
        self.is_editing = not self.is_editing
        self.banner_error = None
        self.banner_warn = None
        self._paint()

    def _insert_text(self, snippet: str) -> None:
        """Insert quick formatting markdown text snippet."""
        current = self.edit_field.value or ""
        self.edit_field.value = current + snippet
        self.page.update()

    def _on_tap_link(self, e: ft.MarkdownLinkClickEvent) -> None:
        """Handle link click inside Markdown preview."""
        url = e.url
        if url:
            self._open_external_url(url)

    def _open_external_url(self, target_url: str | None = None) -> None:
        """Launch web link in external browser."""
        url = target_url or self.save.get("url")
        if url and hasattr(self.page, "launch_url"):
            try:
                self.page.launch_url(url)
            except Exception:
                pass

    async def _save_note(self, _e=None) -> None:
        """Persist note updates via PUT /saves/{id}/note with optimistic locking."""
        if self.is_saving:
            return
        self.is_saving = True
        self.save_btn.disabled = True
        self.banner_error = None
        self.banner_warn = None
        self.page.update()

        new_markdown = (self.edit_field.value or "").strip()
        if not new_markdown:
            self.banner_error = "Note markdown cannot be empty."
            self.is_saving = False
            self.save_btn.disabled = False
            self._paint()
            return

        try:
            res = await self.state.client.put_note(
                save_id=self.save["id"],
                markdown=new_markdown,
                updated_at=self.server_updated_at,
            )
        except Exception as exc:
            self.banner_error = f"Network error saving note: {type(exc).__name__}"
            self.is_saving = False
            self.save_btn.disabled = False
            self._paint()
            return

        self.is_saving = False
        self.save_btn.disabled = False

        if res.status == 409:
            self.banner_warn = (
                "Conflict (409): This note was updated on the server by another client. "
                "Please review your edits and copy any important text before refreshing."
            )
            self._paint()
            return

        if not res.ok:
            self.banner_error = f"Failed to save note: {res.error.message if res.error else 'Validation error'}"
            self._paint()
            return

        # Success: update note data and return to preview
        self.note = res.data if isinstance(res.data, dict) else {}
        self.server_updated_at = self.note.get("updated_at") or self.server_updated_at
        self.is_editing = False

        try:
            self.page.overlay.append(ft.SnackBar(content=ft.Text("Note saved ✓")))
        except Exception:
            pass

        self._paint()

    async def _reprocess_save(self) -> None:
        """Request explicit backend reprocessing for this save."""
        self.banner_warn = "Reprocessing requested…"
        self._paint()
        try:
            res = await self.state.client.reprocess(self.save["id"])
            if res.ok:
                self.banner_warn = "Reprocessing job enqueued. Content will refresh shortly."
            else:
                self.banner_error = f"Reprocess failed: {res.error.message if res.error else 'Error'}"
        except Exception as exc:
            self.banner_error = f"Network error on reprocess: {type(exc).__name__}"
        self._paint()


def open_note_editor(page: ft.Page, state: Any, save: dict, on_closed=None) -> NoteEditorModal:
    """Helper to instantiate and display NoteEditorModal."""
    modal = NoteEditorModal(page, state, save, on_closed=on_closed)
    modal.show()
    return modal
