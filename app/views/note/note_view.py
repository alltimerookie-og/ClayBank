"""Item Note View Shell for ClayBank.

Integrates the full Note experience:
- Header with breadcrumbs, '↩ move' affordance, Edit/Done toggle, and overflow menu.
- Conflict banner and inline delete confirmation with reversible 5s UndoSnackBar.
- Display mode: PropertiesGrid (frontmatter facts) + MarkdownNoteRenderer (GFM body).
- Edit mode: QuickInsertToolbar + Monospace MarkdownNoteEditor with debounced auto-save.
- Bottom sheets: FolderFilingSheet (searchable) and TagEditorSheet (tag chip removal/addition).
- Reprocess action protecting note body.
- 'Open original video' launcher in display mode / 'Done' in edit mode.

Derived from Docs/Phases.md Phase 4, Docs/UIUX.md §6, and Prototype v2 Screen 8.
"""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    CARD_RADIUS,
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_TITLE_LARGE,
    MIN_TOUCH_TARGET,
    PILL_RADIUS,
    SPACING_8,
    SPACING_12,
    SPACING_16,
    SPACING_24,
    create_text_style,
)
from app.ui.snackbar import UndoSnackBar
from app.views.note.folder_sheet import FolderFilingSheet
from app.views.note.note_alerts import ConflictBanner, DeleteConfirmBar
from app.views.note.note_editor import MarkdownNoteEditor
from app.views.note.note_engine import FrontmatterParser
from app.views.note.note_header import NoteHeader
from app.views.note.note_renderer import MarkdownNoteRenderer
from app.views.note.tag_sheet import TagEditorSheet

UNDO_DURATION_MS: int = 5000


class ItemNoteView(ft.Container):
    """Full-featured Item Note View Shell."""

    def __init__(
        self,
        *,
        save_id: str,
        raw_markdown: str,
        save_data: dict[str, Any] | None = None,
        job_data: dict[str, Any] | None = None,
        jump_target: str | None = None,
        available_folders: list[str] | None = None,
        on_back: Callable[[], Any] | None = None,
        on_save_note: Callable[[str, str, str], Any] | None = None,
        on_move_folder: Callable[[str, str | None], Any] | None = None,
        on_update_tags: Callable[[str, list[str]], Any] | None = None,
        on_reprocess: Callable[[str], Any] | None = None,
        on_delete: Callable[[str], Any] | None = None,
        on_restore_delete: Callable[[str], Any] | None = None,
        on_open_url: Callable[[str], Any] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.save_id = save_id
        self.raw_markdown = raw_markdown
        self.save_data = save_data or {}
        self.job_data = job_data or {}
        self.jump_target_val = jump_target
        self.available_folders = available_folders
        self.on_back = on_back
        self.on_save_note = on_save_note
        self.on_move_folder = on_move_folder
        self.on_update_tags = on_update_tags
        self.on_reprocess = on_reprocess
        self.on_delete = on_delete
        self.on_restore_delete = on_restore_delete
        self.on_open_url = on_open_url
        self.theme_mode_val = theme_mode

        self.is_editing = False
        self.is_conflict = False
        self.last_snackbar: UndoSnackBar | None = None

        # Parse initial frontmatter and markdown body
        self.frontmatter, self.clean_body = FrontmatterParser.parse(raw_markdown)

        palette = get_palette(theme_mode)

        # 1. Header
        self.header = NoteHeader(
            folder_path=self.frontmatter.get("folder"),
            is_editing=False,
            on_back=self._handle_back,
            on_toggle_edit=self.set_editing_mode,
            on_move=self.open_folder_sheet,
            on_menu_action=self.handle_menu_action,
            theme_mode=theme_mode,
        )

        # 2. Conflict Banner (hidden by default)
        self.conflict_banner = ConflictBanner(
            on_keep_local=self._handle_keep_local,
            on_discard_local=self._handle_discard_local,
            theme_mode=theme_mode,
        )
        self.conflict_container = ft.Container(
            content=self.conflict_banner,
            visible=False,
            padding=ft.Padding.only(bottom=SPACING_8),
        )

        # 3. Delete Confirm Bar (hidden by default)
        self.delete_confirm_bar = DeleteConfirmBar(
            on_confirm_delete=self._handle_delete_confirmed,
            on_cancel=self._handle_delete_cancelled,
            theme_mode=theme_mode,
        )
        self.delete_container = ft.Container(
            content=self.delete_confirm_bar,
            visible=False,
            padding=ft.Padding.only(bottom=SPACING_8),
        )

        # 4. Display Mode Components: Properties Grid & Markdown Renderer
        from app.views.note.properties_grid import PropertiesGrid

        self.properties_grid = PropertiesGrid(
            frontmatter=self.frontmatter,
            on_edit_folder=self.open_folder_sheet,
            on_edit_tags=self.open_tag_sheet,
            on_open_url=self._handle_open_url,
            theme_mode=theme_mode,
        )

        self.markdown_renderer = MarkdownNoteRenderer(
            markdown=self.clean_body,
            jump_target=jump_target,
            on_tap_link=self._handle_open_url,
            theme_mode=theme_mode,
        )

        self.display_mode_column = ft.Column(
            controls=[
                self.properties_grid,
                self.markdown_renderer,
            ],
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
            spacing=0,
        )

        # 5. Edit Mode Component: MarkdownNoteEditor
        self.markdown_editor = MarkdownNoteEditor(
            save_id=save_id,
            initial_markdown=raw_markdown,
            on_save_note=self._handle_editor_save,
            theme_mode=theme_mode,
        )
        self.edit_mode_container = ft.Container(
            content=self.markdown_editor,
            expand=True,
            visible=False,
        )

        # 6. Bottom Action Button ("Open original video" in display / "Done" in edit)
        video_url = self.frontmatter.get("video_url") or ""
        self.bottom_button = ft.FilledButton(
            "Open original video",
            style=ft.ButtonStyle(
                bgcolor=palette["accent"],
                color=palette["accent_fg"],
            ),
            height=MIN_TOUCH_TARGET,
            on_click=lambda _: self._handle_bottom_action(),
        )

        bottom_bar = ft.Container(
            content=ft.Row(
                controls=[self.bottom_button],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(vertical=SPACING_8),
        )

        # Main viewport layout
        main_layout = ft.Column(
            controls=[
                self.header,
                self.conflict_container,
                self.delete_container,
                ft.Container(
                    content=ft.Stack(
                        controls=[
                            self.display_mode_column,
                            self.edit_mode_container,
                        ],
                        expand=True,
                    ),
                    expand=True,
                    padding=ft.Padding.symmetric(horizontal=SPACING_16),
                ),
                bottom_bar,
            ],
            expand=True,
            spacing=0,
        )

        # Overlay container for modal bottom sheets
        self.overlay_container = ft.Container(visible=False)

        super().__init__(
            content=ft.Stack(
                controls=[
                    main_layout,
                    self.overlay_container,
                ],
                expand=True,
            ),
            expand=True,
            bgcolor=palette["background"],
        )

    def set_editing_mode(self, is_editing: bool) -> None:
        """Switch between Display Mode and Edit Mode."""
        self.is_editing = is_editing
        self.header.set_editing(is_editing)

        palette = get_palette(self.theme_mode_val)

        if is_editing:
            # Entering Edit Mode: pass full serialized raw markdown to editor
            full_md = FrontmatterParser.serialize(self.frontmatter, self.clean_body)
            self.markdown_editor.set_content(full_md)
            self.display_mode_column.visible = False
            self.edit_mode_container.visible = True
            self.bottom_button.content = "Done"
        else:
            # Exiting Edit Mode: flush editor and re-parse frontmatter/body
            self.markdown_editor.flush_pending_save()
            updated_raw = self.markdown_editor.current_markdown
            self.raw_markdown = updated_raw
            self.frontmatter, self.clean_body = FrontmatterParser.parse(updated_raw)

            # Update display components
            self.header.set_folder_path(self.frontmatter.get("folder"))
            self.properties_grid.set_frontmatter(self.frontmatter)
            self.markdown_renderer.set_markdown(self.clean_body, self.jump_target_val)

            self.display_mode_column.visible = True
            self.edit_mode_container.visible = False
            self.bottom_button.content = "Open original video"

    def handle_menu_action(self, action: str) -> None:
        """Handle actions dispatched from overflow menu."""
        if action == "move":
            self.open_folder_sheet()
        elif action == "tags":
            self.open_tag_sheet()
        elif action == "reprocess":
            self._handle_reprocess()
        elif action == "delete":
            self.delete_container.visible = True

    def open_folder_sheet(self) -> None:
        """Open the searchable FolderFilingSheet."""
        sheet = FolderFilingSheet(
            current_folder=self.frontmatter.get("folder"),
            available_folders=self.available_folders,
            on_select_folder=self._handle_folder_selected,
            on_cancel=self.close_overlay,
            theme_mode=self.theme_mode_val,
        )
        self.overlay_container.content = sheet
        self.overlay_container.visible = True

    def open_tag_sheet(self) -> None:
        """Open the TagEditorSheet."""
        sheet = TagEditorSheet(
            current_tags=self.frontmatter.get("tags"),
            on_save_tags=self._handle_tags_saved,
            on_cancel=self.close_overlay,
            theme_mode=self.theme_mode_val,
        )
        self.overlay_container.content = sheet
        self.overlay_container.visible = True

    def close_overlay(self) -> None:
        """Dismiss active modal bottom sheet."""
        self.overlay_container.visible = False
        self.overlay_container.content = None

    def _handle_folder_selected(self, new_folder: str | None) -> None:
        """Update folder frontmatter, refresh views, and emit UndoSnackBar."""
        old_folder = self.frontmatter.get("folder")
        self.frontmatter["folder"] = new_folder
        self.raw_markdown = FrontmatterParser.serialize(self.frontmatter, self.clean_body)

        self.header.set_folder_path(new_folder)
        self.properties_grid.set_frontmatter(self.frontmatter)
        self.close_overlay()

        if self.on_move_folder is not None:
            self.on_move_folder(self.save_id, new_folder)

        folder_label = new_folder if new_folder else "Inbox"
        self.last_snackbar = UndoSnackBar(
            message=f"Moved to {folder_label}",
            duration_ms=UNDO_DURATION_MS,
            on_undo=lambda _: self._revert_folder_move(old_folder),
            theme_mode=self.theme_mode_val,
        )

    def _revert_folder_move(self, previous_folder: str | None) -> None:
        """Revert folder move on Undo tap."""
        self.frontmatter["folder"] = previous_folder
        self.raw_markdown = FrontmatterParser.serialize(self.frontmatter, self.clean_body)
        self.header.set_folder_path(previous_folder)
        self.properties_grid.set_frontmatter(self.frontmatter)

        if self.on_move_folder is not None:
            self.on_move_folder(self.save_id, previous_folder)

    def _handle_tags_saved(self, new_tags: list[str]) -> None:
        """Update tags frontmatter, refresh views, and emit UndoSnackBar."""
        old_tags = list(self.frontmatter.get("tags") or [])
        self.frontmatter["tags"] = new_tags
        self.raw_markdown = FrontmatterParser.serialize(self.frontmatter, self.clean_body)

        self.properties_grid.set_frontmatter(self.frontmatter)
        self.close_overlay()

        if self.on_update_tags is not None:
            self.on_update_tags(self.save_id, new_tags)

        self.last_snackbar = UndoSnackBar(
            message="Tags saved",
            duration_ms=UNDO_DURATION_MS,
            on_undo=lambda _: self._revert_tags_update(old_tags),
            theme_mode=self.theme_mode_val,
        )

    def _revert_tags_update(self, previous_tags: list[str]) -> None:
        """Revert tags change on Undo tap."""
        self.frontmatter["tags"] = previous_tags
        self.raw_markdown = FrontmatterParser.serialize(self.frontmatter, self.clean_body)
        self.properties_grid.set_frontmatter(self.frontmatter)

        if self.on_update_tags is not None:
            self.on_update_tags(self.save_id, previous_tags)

    def _handle_reprocess(self) -> None:
        """Trigger reprocess pipeline while protecting note body content."""
        if self.on_reprocess is not None:
            self.on_reprocess(self.save_id)

        self.last_snackbar = UndoSnackBar(
            message="Reprocessing: metadata and transcript only — the note body is never touched",
            duration_ms=UNDO_DURATION_MS,
            theme_mode=self.theme_mode_val,
        )

    def _handle_delete_confirmed(self) -> None:
        """Handle confirmed deletion: hide note body and trigger undo snackbar."""
        self.display_mode_column.visible = False
        self.edit_mode_container.visible = False
        self.bottom_button.visible = False

        if self.on_delete is not None:
            self.on_delete(self.save_id)

        self.last_snackbar = UndoSnackBar(
            message="Note deleted",
            duration_ms=UNDO_DURATION_MS,
            on_undo=lambda _: self._restore_deleted_note(),
            theme_mode=self.theme_mode_val,
        )

    def _restore_deleted_note(self) -> None:
        """Restore note view on delete undo."""
        self.delete_confirm_bar.reset_state()
        self.delete_container.visible = False
        self.display_mode_column.visible = True
        self.bottom_button.visible = True

        if self.on_restore_delete is not None:
            self.on_restore_delete(self.save_id)

    def _handle_delete_cancelled(self) -> None:
        """Dismiss delete confirmation card without deleting."""
        self.delete_container.visible = False

    def _handle_keep_local(self) -> None:
        """Dismiss conflict banner keeping local edits."""
        self.conflict_container.visible = False
        self.is_conflict = False

    def _handle_discard_local(self) -> None:
        """Discard local changes and reload from server."""
        self.conflict_container.visible = False
        self.is_conflict = False

    def _handle_bottom_action(self) -> None:
        """Handle tap on bottom action button."""
        if self.is_editing:
            self.set_editing_mode(False)
        else:
            url = self.frontmatter.get("video_url") or ""
            self._handle_open_url(url)

    def _handle_open_url(self, url: str) -> None:
        """Launch URL via callback or snackbar fallback."""
        if not url:
            return
        if self.on_open_url is not None:
            self.on_open_url(url)
        else:
            self.last_snackbar = UndoSnackBar(
                message=f"Opens original link: {url}",
                duration_ms=UNDO_DURATION_MS,
                theme_mode=self.theme_mode_val,
            )

    def _handle_back(self) -> None:
        """Handle back button navigation."""
        if self.is_editing:
            self.set_editing_mode(False)
        if self.on_back is not None:
            self.on_back()

    def _handle_editor_save(self, save_id: str, markdown: str, updated_at: str) -> Any:
        """Forward editor auto-save to callback."""
        if self.on_save_note is not None:
            return self.on_save_note(save_id, markdown, updated_at)
        return {"status": "saved"}
