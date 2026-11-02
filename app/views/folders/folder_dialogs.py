"""Folder creation, rename, delete confirmation, and context menu dialogs.

Adheres strictly to ClayBank design system and rules:
- Max folder depth <= 3 (Docs/Rules.md §3, folder-write.json).
- Reserved names rejected: ["Other", "Misc", "Unsorted", "Inbox"] (Docs/Rules.md §3).
- Deletion preserves saves by returning them to Inbox (Docs/UIUX.md §7).
"""

from __future__ import annotations

from typing import Any, Callable, Sequence
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_MUTED,
    FONT_SIZE_TITLE_LARGE,
    SPACING_8,
    SPACING_12,
    SPACING_16,
    create_text_style,
)
from app.ui.card import ClaySheet
from app.ui.chips import FolderChip

RESERVED_FOLDER_NAMES = frozenset({"other", "misc", "unsorted", "inbox"})
MAX_FOLDER_DEPTH = 3


def validate_folder_name(
    name: str | None,
    existing_names: Sequence[str] | None = None,
) -> tuple[bool, str | None]:
    """Validate a proposed folder name against ClayBank business rules."""
    if not name or not name.strip():
        return False, "Folder name cannot be empty."

    trimmed = name.strip()
    if trimmed.lower() in RESERVED_FOLDER_NAMES:
        return False, f"'{trimmed}' is a reserved folder name."

    if existing_names:
        existing_lower = {n.strip().lower() for n in existing_names if n}
        if trimmed.lower() in existing_lower:
            return False, "A folder with this name already exists."

    return True, None


def validate_folder_depth(parent_depth: int) -> tuple[bool, str | None]:
    """Validate folder nesting depth. Maximum allowed depth is 3."""
    if parent_depth >= MAX_FOLDER_DEPTH:
        return False, f"Folders cannot exceed {MAX_FOLDER_DEPTH} levels of depth."
    return True, None


class CreateFolderSheet(ClaySheet):
    """Bottom sheet modal for creating a root folder or subfolder."""

    def __init__(
        self,
        *,
        parent_id: str | None = None,
        parent_name: str | None = None,
        parent_depth: int = 1,
        existing_names: Sequence[str] | None = None,
        on_create: Callable[[dict[str, Any]], None] | None = None,
        on_cancel: Callable[[], None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.parent_id = parent_id
        self.parent_name = parent_name
        self.parent_depth = parent_depth
        self.existing_names = list(existing_names) if existing_names else []
        self.on_create = on_create
        self.on_cancel = on_cancel
        self.theme_mode_val = theme_mode

        palette = get_palette(theme_mode)

        # Drag handle
        drag_handle = ft.Container(
            width=36.0,
            height=4.0,
            border_radius=ft.BorderRadius.all(2.0),
            bgcolor=palette["line"],
            alignment=ft.Alignment(0, 0),
        )

        title_str = f"New Subfolder in {parent_name}" if parent_name else "New folder"
        self.title_text = ft.Text(
            title_str,
            style=create_text_style(
                size=FONT_SIZE_TITLE_LARGE,
                weight=ft.FontWeight.BOLD,
                color=palette["ink"],
            ),
        )

        self.name_field = ft.TextField(
            hint_text="Folder name",
            autofocus=True,
            border_color=palette["line"],
            focused_border_color=palette["accent"],
            text_style=ft.TextStyle(
                font_family=FONT_FAMILY_UI,
                size=FONT_SIZE_BODY,
                color=palette["ink"],
            ),
            cursor_color=palette["accent"],
            on_submit=lambda e: self._submit(),
        )

        self.error_text = ft.Text(
            "",
            color=palette["accent"],
            size=FONT_SIZE_MUTED,
            visible=False,
        )

        controls: list[ft.Control] = [
            ft.Row(controls=[drag_handle], alignment=ft.MainAxisAlignment.CENTER),
            self.title_text,
        ]

        if parent_name:
            controls.append(
                FolderChip(
                    path=parent_name,
                    prefix="Parent: ",
                    theme_mode=theme_mode,
                )
            )

        controls.extend([self.name_field, self.error_text])

        # Action buttons
        self.cancel_button = ft.TextButton(
            "Cancel",
            on_click=lambda e: self._cancel(),
            style=ft.ButtonStyle(color=palette["muted"]),
        )
        self.create_button = ft.FilledButton(
            "Create",
            on_click=lambda e: self._submit(),
            style=ft.ButtonStyle(
                bgcolor=palette["accent"],
                color=palette["accent_fg"],
            ),
        )

        buttons_row = ft.Row(
            controls=[self.cancel_button, self.create_button],
            alignment=ft.MainAxisAlignment.END,
            spacing=SPACING_8,
        )
        controls.append(buttons_row)

        content_col = ft.Column(
            controls=controls,
            spacing=SPACING_12,
            tight=True,
        )

        super().__init__(
            content=content_col,
            padding=SPACING_16,
            theme_mode=theme_mode,
        )

    def _cancel(self) -> None:
        if self.on_cancel:
            self.on_cancel()

    def _submit(self) -> None:
        # Check depth first
        if self.parent_id and self.parent_depth >= MAX_FOLDER_DEPTH:
            depth_ok, depth_err = validate_folder_depth(self.parent_depth)
            if not depth_ok:
                self.error_text.value = depth_err or "Max depth exceeded"
                self.error_text.visible = True
                try:
                    self.update()
                except Exception:
                    pass
                return

        name = self.name_field.value
        is_valid, err_msg = validate_folder_name(name, self.existing_names)
        if not is_valid:
            self.error_text.value = err_msg or "Invalid folder name"
            self.error_text.visible = True
            try:
                self.update()
            except Exception:
                pass
            return

        self.error_text.visible = False
        payload = {
            "name": name.strip() if name else "",
            "parent_id": self.parent_id,
        }
        if self.on_create:
            self.on_create(payload)


class RenameFolderSheet(ClaySheet):
    """Bottom sheet modal for renaming an existing folder."""

    def __init__(
        self,
        folder_data: dict[str, Any],
        *,
        existing_names: Sequence[str] | None = None,
        on_rename: Callable[[str, str], None] | None = None,
        on_cancel: Callable[[], None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.folder_data = dict(folder_data)
        self.folder_id = str(folder_data.get("id") or "")
        self.current_name = str(folder_data.get("name") or "")
        self.existing_names = list(existing_names) if existing_names else []
        self.on_rename = on_rename
        self.on_cancel = on_cancel

        palette = get_palette(theme_mode)

        drag_handle = ft.Container(
            width=36.0,
            height=4.0,
            border_radius=ft.BorderRadius.all(2.0),
            bgcolor=palette["line"],
            alignment=ft.Alignment(0, 0),
        )

        self.title_text = ft.Text(
            f"Rename '{self.current_name}'",
            style=create_text_style(
                size=FONT_SIZE_TITLE_LARGE,
                weight=ft.FontWeight.BOLD,
                color=palette["ink"],
            ),
        )

        self.name_field = ft.TextField(
            value=self.current_name,
            hint_text="New folder name",
            autofocus=True,
            border_color=palette["line"],
            focused_border_color=palette["accent"],
            text_style=ft.TextStyle(
                font_family=FONT_FAMILY_UI,
                size=FONT_SIZE_BODY,
                color=palette["ink"],
            ),
            cursor_color=palette["accent"],
            on_submit=lambda e: self._submit(),
        )

        self.error_text = ft.Text(
            "",
            color=palette["accent"],
            size=FONT_SIZE_MUTED,
            visible=False,
        )

        self.cancel_button = ft.TextButton(
            "Cancel",
            on_click=lambda e: self._cancel(),
            style=ft.ButtonStyle(color=palette["muted"]),
        )
        self.save_button = ft.FilledButton(
            "Save",
            on_click=lambda e: self._submit(),
            style=ft.ButtonStyle(
                bgcolor=palette["accent"],
                color=palette["accent_fg"],
            ),
        )

        buttons_row = ft.Row(
            controls=[self.cancel_button, self.save_button],
            alignment=ft.MainAxisAlignment.END,
            spacing=SPACING_8,
        )

        content_col = ft.Column(
            controls=[
                ft.Row(controls=[drag_handle], alignment=ft.MainAxisAlignment.CENTER),
                self.title_text,
                self.name_field,
                self.error_text,
                buttons_row,
            ],
            spacing=SPACING_12,
            tight=True,
        )

        super().__init__(
            content=content_col,
            padding=SPACING_16,
            theme_mode=theme_mode,
        )

    def _cancel(self) -> None:
        if self.on_cancel:
            self.on_cancel()

    def _submit(self) -> None:
        name = self.name_field.value
        trimmed = name.strip() if name else ""

        if trimmed == self.current_name:
            self._cancel()
            return

        other_existing = [n for n in self.existing_names if n.lower() != self.current_name.lower()]
        is_valid, err_msg = validate_folder_name(trimmed, other_existing)
        if not is_valid:
            self.error_text.value = err_msg or "Invalid folder name"
            self.error_text.visible = True
            try:
                self.update()
            except Exception:
                pass
            return

        self.error_text.visible = False
        if self.on_rename:
            self.on_rename(self.folder_id, trimmed)


class DeleteFolderConfirmDialog(ft.AlertDialog):
    """Confirmation modal dialog for deleting a folder, noting saves return to Inbox."""

    def __init__(
        self,
        folder_data: dict[str, Any],
        *,
        on_confirm_delete: Callable[[str], None] | None = None,
        on_cancel: Callable[[], None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.folder_data = dict(folder_data)
        self.folder_id = str(folder_data.get("id") or "")
        self.folder_name = str(folder_data.get("name") or "Folder")
        self.on_confirm_delete = on_confirm_delete
        self.on_cancel = on_cancel

        palette = get_palette(theme_mode)

        title_control = ft.Text(
            f"Delete '{self.folder_name}'?",
            style=create_text_style(
                size=FONT_SIZE_TITLE_LARGE,
                weight=ft.FontWeight.BOLD,
                color=palette["ink"],
            ),
        )

        content_control = ft.Text(
            f"Saves inside '{self.folder_name}' will not be deleted. "
            "They will return unfiled to your Inbox.",
            style=create_text_style(
                size=FONT_SIZE_BODY,
                color=palette["muted"],
            ),
        )

        cancel_btn = ft.TextButton(
            "Cancel",
            on_click=lambda e: self._cancel(),
            style=ft.ButtonStyle(color=palette["muted"]),
        )
        delete_btn = ft.FilledButton(
            "Delete Folder",
            on_click=lambda e: self._confirm(),
            style=ft.ButtonStyle(
                bgcolor=palette["accent"],
                color=palette["accent_fg"],
            ),
        )

        super().__init__(
            title=title_control,
            content=content_control,
            actions=[cancel_btn, delete_btn],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def _cancel(self) -> None:
        if self.on_cancel:
            self.on_cancel()

    def _confirm(self) -> None:
        if self.on_confirm_delete:
            self.on_confirm_delete(self.folder_id)


class FolderContextMenu(ClaySheet):
    """Context action sheet for folder card actions (open, rename, subfolder, delete)."""

    def __init__(
        self,
        folder_data: dict[str, Any],
        *,
        folder_depth: int = 1,
        on_open: Callable[[dict[str, Any]], None] | None = None,
        on_rename: Callable[[dict[str, Any]], None] | None = None,
        on_add_subfolder: Callable[[dict[str, Any]], None] | None = None,
        on_delete: Callable[[dict[str, Any]], None] | None = None,
        on_cancel: Callable[[], None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.folder_data = dict(folder_data)
        self.folder_name = str(folder_data.get("name") or "Folder")
        self.folder_depth = folder_depth
        self.on_open = on_open
        self.on_rename = on_rename
        self.on_add_subfolder = on_add_subfolder
        self.on_delete = on_delete
        self.on_cancel = on_cancel

        palette = get_palette(theme_mode)

        drag_handle = ft.Container(
            width=36.0,
            height=4.0,
            border_radius=ft.BorderRadius.all(2.0),
            bgcolor=palette["line"],
            alignment=ft.Alignment(0, 0),
        )

        title_text = ft.Text(
            self.folder_name,
            style=create_text_style(
                size=FONT_SIZE_TITLE_LARGE,
                weight=ft.FontWeight.BOLD,
                color=palette["ink"],
            ),
        )

        items: list[ft.Control] = [
            ft.Row(controls=[drag_handle], alignment=ft.MainAxisAlignment.CENTER),
            title_text,
            ft.ListTile(
                leading=ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, color=palette["ink"]),
                title=ft.Text("Open folder", color=palette["ink"]),
                on_click=lambda e: self.on_open(self.folder_data) if self.on_open else None,
            ),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.EDIT_ROUNDED, color=palette["ink"]),
                title=ft.Text("Rename", color=palette["ink"]),
                on_click=lambda e: self.on_rename(self.folder_data) if self.on_rename else None,
            ),
        ]

        # Add subfolder only if depth < 3
        if folder_depth < MAX_FOLDER_DEPTH:
            items.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.CREATE_NEW_FOLDER_ROUNDED, color=palette["ink"]),
                    title=ft.Text("Add subfolder", color=palette["ink"]),
                    on_click=lambda e: (
                        self.on_add_subfolder(self.folder_data) if self.on_add_subfolder else None
                    ),
                )
            )

        items.append(
            ft.ListTile(
                leading=ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED, color=palette["accent"]),
                title=ft.Text("Delete folder", color=palette["accent"]),
                on_click=lambda e: self.on_delete(self.folder_data) if self.on_delete else None,
            )
        )

        content_col = ft.Column(
            controls=items,
            spacing=SPACING_8,
            tight=True,
        )

        super().__init__(
            content=content_col,
            padding=SPACING_16,
            theme_mode=theme_mode,
        )
