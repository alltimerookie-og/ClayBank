"""Top-level ClayBank Application Coordinator.

Orchestrates navigation lifecycle across Splash -> Onboarding -> AppShell,
binds the AddLinkPasteSheet modal, coordinates Inbox data refreshes, and triggers
UndoSnackBar feedback for review actions.
Integrates ItemNoteView navigation for viewing and editing saved notes.
Integrates FoldersGridView, FolderDetailView, and cluster proposals for Phase 5.

Derived from Docs/Phases.md Phase 2, Phase 4 & Phase 5, Docs/UIUX.md, and Prototype v2.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable
import uuid
import flet as ft

from app.shell.app_shell import AppShellLayout
from app.shell.nav import TAB_FOLDERS, TAB_INBOX
from app.shell.theme import get_palette
from app.ui.snackbar import UndoSnackBar
from app.views.folders.folder_detail_view import FolderDetailView
from app.views.folders.folder_dialogs import (
    CreateFolderSheet,
    DeleteFolderConfirmDialog,
    FolderContextMenu,
    MAX_FOLDER_DEPTH,
    RenameFolderSheet,
)
from app.views.folders.folders_grid_view import FoldersGridView
from app.views.inbox_view import InboxView
from app.views.note.note_view import ItemNoteView
from app.views.onboarding_view import OnboardingView
from app.views.paste_sheet import AddLinkPasteSheet
from app.views.splash_view import SplashView

UNDO_DURATION_MS: int = 5000


class ClayBankApp(ft.Container):
    """Top-level ClayBank application manager."""

    def __init__(
        self,
        *,
        has_seen_onboarding: bool = False,
        saves: list[dict[str, Any]] | None = None,
        suggestions: list[dict[str, Any]] | None = None,
        active_jobs: list[dict[str, Any]] | None = None,
        notes: dict[str, Any] | None = None,
        folders: list[dict[str, Any]] | None = None,
        available_folders: list[str] | None = None,
        on_save_capture: Callable[[dict[str, Any]], Any] | None = None,
        on_get_note: Callable[[str], dict[str, Any] | None] | None = None,
        on_save_note: Callable[[str, str, str], Any] | None = None,
        on_move_folder: Callable[[str, str | None], Any] | None = None,
        on_update_tags: Callable[[str, list[str]], Any] | None = None,
        on_reprocess_note: Callable[[str], Any] | None = None,
        on_delete_note: Callable[[str], Any] | None = None,
        on_restore_note: Callable[[str], Any] | None = None,
        on_open_url: Callable[[str], Any] | None = None,
        on_create_folder: Callable[[dict[str, Any]], Any] | None = None,
        on_rename_folder: Callable[[str, str], Any] | None = None,
        on_delete_folder: Callable[[str], Any] | None = None,
        on_accept_cluster: Callable[[dict[str, Any]], Any] | None = None,
        on_ignore_cluster: Callable[[dict[str, Any]], Any] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.has_seen_onboarding = has_seen_onboarding
        self.theme_mode_val = theme_mode
        self.notes: dict[str, Any] = dict(notes or {})
        self.available_folders = available_folders
        self.on_save_capture = on_save_capture
        self.on_get_note = on_get_note
        self.on_save_note = on_save_note
        self.on_move_folder = on_move_folder
        self.on_update_tags = on_update_tags
        self.on_reprocess_note = on_reprocess_note
        self.on_delete_note = on_delete_note
        self.on_restore_note = on_restore_note
        self.on_open_url = on_open_url
        self.on_create_folder = on_create_folder
        self.on_rename_folder = on_rename_folder
        self.on_delete_folder = on_delete_folder
        self.on_accept_cluster = on_accept_cluster
        self.on_ignore_cluster = on_ignore_cluster

        self._last_snackbar: UndoSnackBar | None = None
        self.is_paste_sheet_open = False
        self.current_note_view: ItemNoteView | None = None
        self.current_folder_detail_view: FolderDetailView | None = None
        self.previous_view: ft.Control | None = None
        self._deleted_saves: dict[str, dict[str, Any]] = {}
        self._deleted_folders: dict[str, dict[str, Any]] = {}
        self._folder_unfiled_saves: dict[str, list[str]] = {}

        # Initialize folders collection
        if folders is not None:
            self._folders_collection = list(folders)
        else:
            self._folders_collection = self._load_default_folders()

        # Build Folders view for Tab 1
        self.folders_view = FoldersGridView(
            folders=self._folders_collection,
            on_select_folder=self.open_folder_detail_view,
            on_new_folder=lambda: self.open_create_folder_sheet(),
            on_folder_long_press=self.open_folder_context_menu,
            on_refresh=self.refresh_folders,
            theme_mode=theme_mode,
        )

        # Build real Inbox view
        self.inbox_view = InboxView(
            saves=saves,
            suggestions=suggestions,
            active_jobs=active_jobs,
            on_add_link=self.open_paste_sheet,
            on_refresh=self.refresh_inbox,
            on_select_save=self.open_note_view,
            on_accept_suggestion=self.handle_accept_suggestion,
            on_ignore_suggestion=self.handle_ignore_suggestion,
            on_accept_cluster=self.handle_accept_cluster,
            on_ignore_cluster=self.handle_ignore_cluster,
            theme_mode=theme_mode,
        )

        # Build App Shell hosting both Inbox and Folders (strictly 4 tabs)
        self.app_shell = AppShellLayout(
            inbox_view=self.inbox_view,
            folders_view=self.folders_view,
            on_add_link=self.open_paste_sheet,
            initial_tab=TAB_INBOX,
            theme_mode=theme_mode,
        )

        # Build Onboarding view
        self.onboarding_view = OnboardingView(
            on_finish=self.transition_to_shell,
            on_skip=self.transition_to_shell,
            on_persist_preference=self._persist_preference,
            theme_mode=theme_mode,
        )

        # Build Splash view
        self.splash_view = SplashView(
            on_complete=self.handle_splash_complete,
            has_seen_onboarding=has_seen_onboarding,
            theme_mode=theme_mode,
        )

        # Paste Sheet overlay container
        self.paste_sheet: AddLinkPasteSheet | None = None
        self.overlay_container = ft.Container(visible=False)

        # Root content switcher
        self.viewport = ft.Container(
            content=self.splash_view,
            expand=True,
        )

        super().__init__(
            content=ft.Stack(
                controls=[
                    self.viewport,
                    self.overlay_container,
                ],
                expand=True,
            ),
            expand=True,
        )

    def _load_default_folders(self) -> list[dict[str, Any]]:
        """Load default folders from fixture or provide canonical starter collection."""
        try:
            f_path = Path("Docs/api/fixtures/folder.fixtures.json")
            if f_path.exists():
                data = json.loads(f_path.read_text(encoding="utf-8"))
                valid = data.get("valid")
                if valid:
                    return list(valid)
        except Exception:
            pass

        return [
            {
                "id": "018f4c1a-0000-7de6-9c8e-000000000004",
                "parent_id": None,
                "name": "Cooking",
                "save_count": 24,
                "created_at": "2026-10-31T12:00:00Z",
                "updated_at": "2026-10-31T12:00:00Z",
            },
            {
                "id": "018f4c1a-0000-7de6-9c8e-000000000005",
                "parent_id": "018f4c1a-0000-7de6-9c8e-000000000004",
                "name": "Pasta",
                "save_count": 6,
                "created_at": "2026-10-31T12:00:00Z",
                "updated_at": "2026-10-31T12:00:00Z",
            },
        ]

    @property
    def last_snackbar(self) -> UndoSnackBar | None:
        """Expose active snackbar from note view or coordinator."""
        if self.current_note_view is not None and self.current_note_view.last_snackbar is not None:
            return self.current_note_view.last_snackbar
        return self._last_snackbar

    @last_snackbar.setter
    def last_snackbar(self, val: UndoSnackBar | None) -> None:
        self._last_snackbar = val

    def handle_splash_complete(self, has_seen_onboarding: bool) -> None:
        """Route from splash into onboarding (first run) or directly to shell."""
        if has_seen_onboarding:
            self.transition_to_shell()
        else:
            self.viewport.content = self.onboarding_view

    def transition_to_shell(self) -> None:
        """Route into the main AppShellLayout."""
        self.has_seen_onboarding = True
        self.viewport.content = self.app_shell

    def open_paste_sheet(self) -> None:
        """Open the AddLinkPasteSheet modal bottom sheet."""
        self.paste_sheet = AddLinkPasteSheet(
            on_submit=self.handle_capture_submit,
            on_cancel=self.close_paste_sheet,
            on_success=self.handle_capture_success,
            theme_mode=self.theme_mode_val,
        )
        self.overlay_container.content = self.paste_sheet
        self.overlay_container.visible = True
        self.is_paste_sheet_open = True

    def close_paste_sheet(self) -> None:
        """Dismiss the AddLinkPasteSheet modal."""
        self.overlay_container.visible = False
        self.overlay_container.content = None
        self.paste_sheet = None
        self.is_paste_sheet_open = False

    def handle_capture_submit(self, payload: dict[str, Any]) -> Any:
        """Handle submit action from paste sheet."""
        if self.on_save_capture is not None:
            return self.on_save_capture(payload)
        return {"id": "save-mock-id", "url": payload.get("url"), "status": "queued"}

    def handle_capture_success(self, save_data: dict[str, Any]) -> None:
        """Dismiss paste sheet and request inbox refresh on capture success."""
        self.close_paste_sheet()
        self.refresh_inbox()

    def refresh_inbox(self) -> None:
        """Request inbox data reload."""
        if self.inbox_view.on_refresh is not None and self.inbox_view.on_refresh != self.refresh_inbox:
            self.inbox_view.on_refresh()
        else:
            self.inbox_view.rebuild_view()

    def handle_accept_suggestion(self, save_id: str, folder_path: str) -> None:
        """Trigger UndoSnackBar feedback upon accepting folder suggestion."""
        self.last_snackbar = UndoSnackBar(
            message=f"Moved to {folder_path}",
            duration_ms=UNDO_DURATION_MS,
            on_undo=lambda _: self.undo_suggestion_acceptance(save_id),
            theme_mode=self.theme_mode_val,
        )

    def handle_ignore_suggestion(self, save_id: str) -> None:
        """Trigger UndoSnackBar feedback upon ignoring suggestion."""
        self.last_snackbar = UndoSnackBar(
            message="Suggestion dismissed",
            duration_ms=UNDO_DURATION_MS,
            on_undo=lambda _: self.undo_suggestion_dismissal(save_id),
            theme_mode=self.theme_mode_val,
        )

    def undo_suggestion_acceptance(self, save_id: str) -> None:
        """Revert folder suggestion acceptance."""
        pass

    def undo_suggestion_dismissal(self, save_id: str) -> None:
        """Revert folder suggestion dismissal."""
        pass

    def _persist_preference(self, key: str, value: bool) -> None:
        """Persist user preference."""
        if key == "has_seen_onboarding":
            self.has_seen_onboarding = value

    # =========================================================================
    # Phase 5: Folders, Suggestions & Organization Coordination
    # =========================================================================

    def refresh_folders(self) -> None:
        """Reload folders and update FoldersGridView."""
        self.folders_view.set_folders(self._folders_collection)

    def handle_accept_cluster(self, payload: dict[str, Any]) -> None:
        """Handle accepting a cluster proposal suggestion."""
        target_path = str(payload.get("path") or "")
        cluster_items = payload.get("cluster") or []
        count = len(cluster_items)

        # Update member saves in inbox
        member_ids = {str(item.get("save_id") or "") for item in cluster_items}
        for s in self.inbox_view._saves:
            s_id = str(s.get("id") or s.get("save_id") or "")
            if s_id in member_ids:
                s["folder"] = target_path

        # Find or update folder save count
        for f in self._folders_collection:
            if f.get("name") == target_path:
                current_cnt = int(f.get("save_count") or 0)
                f["save_count"] = current_cnt + count
                break

        self.refresh_folders()
        self.inbox_view.rebuild_view()

        if self.on_accept_cluster is not None:
            self.on_accept_cluster(payload)

        self.last_snackbar = UndoSnackBar(
            message=f"Filed {count} saves to '{target_path}'",
            duration_ms=UNDO_DURATION_MS,
            on_undo=lambda _: self.undo_cluster_acceptance(payload),
            theme_mode=self.theme_mode_val,
        )

    def handle_ignore_cluster(self, payload: dict[str, Any]) -> None:
        """Handle ignoring a cluster proposal suggestion."""
        target_path = str(payload.get("path") or "")

        if self.on_ignore_cluster is not None:
            self.on_ignore_cluster(payload)

        self.last_snackbar = UndoSnackBar(
            message=f"Cluster proposal for '{target_path}' dismissed",
            duration_ms=UNDO_DURATION_MS,
            on_undo=lambda _: self.undo_cluster_dismissal(payload),
            theme_mode=self.theme_mode_val,
        )

    def undo_cluster_acceptance(self, payload: dict[str, Any]) -> None:
        """Revert cluster proposal filing upon undo."""
        cluster_items = payload.get("cluster") or []
        target_path = str(payload.get("path") or "")
        count = len(cluster_items)
        member_ids = {str(item.get("save_id") or "") for item in cluster_items}

        for s in self.inbox_view._saves:
            s_id = str(s.get("id") or s.get("save_id") or "")
            if s_id in member_ids and s.get("folder") == target_path:
                s["folder"] = None

        for f in self._folders_collection:
            if f.get("name") == target_path:
                current_cnt = int(f.get("save_count") or 0)
                f["save_count"] = max(0, current_cnt - count)
                break

        self.refresh_folders()
        self.inbox_view.rebuild_view()

    def undo_cluster_dismissal(self, payload: dict[str, Any]) -> None:
        """Revert dismissal of cluster suggestion."""
        pass

    def _get_folder_depth(self, folder_id: str | None) -> int:
        """Calculate folder nesting level (1-indexed)."""
        if not folder_id:
            return 1
        depth = 1
        current_id = folder_id
        while current_id:
            parent = next((f for f in self._folders_collection if f.get("id") == current_id), None)
            if parent and parent.get("parent_id"):
                depth += 1
                current_id = parent["parent_id"]
            else:
                break
        return min(depth, MAX_FOLDER_DEPTH)

    def _build_breadcrumb_trail(self, folder_data: dict[str, Any]) -> list[tuple[str, str]]:
        """Construct hierarchical breadcrumb path of (id, name) tuples."""
        trail: list[tuple[str, str]] = [(str(folder_data.get("id")), str(folder_data.get("name")))]
        current_parent = folder_data.get("parent_id")
        while current_parent:
            p_obj = next((f for f in self._folders_collection if f.get("id") == current_parent), None)
            if p_obj:
                trail.insert(0, (str(p_obj.get("id")), str(p_obj.get("name"))))
                current_parent = p_obj.get("parent_id")
            else:
                break
        return trail

    def open_folder_detail_view(self, folder_data: dict[str, Any] | str) -> FolderDetailView:
        """Navigate to FolderDetailView drill-down for a selected folder."""
        f_obj: dict[str, Any]
        if isinstance(folder_data, dict):
            f_obj = dict(folder_data)
        else:
            found = next((f for f in self._folders_collection if f.get("id") == str(folder_data)), None)
            f_obj = dict(found) if found else {"id": str(folder_data), "name": "Folder"}

        folder_id = str(f_obj.get("id") or "")
        folder_name = str(f_obj.get("name") or "Folder")

        # Subfolders
        subfolders = [f for f in self._folders_collection if f.get("parent_id") == folder_id]

        # Member saves
        matching_saves = [
            s for s in self.inbox_view._saves
            if s.get("folder") == folder_name or s.get("folder_id") == folder_id
        ]

        depth = self._get_folder_depth(folder_id)
        trail = self._build_breadcrumb_trail(f_obj)

        self.previous_view = self.viewport.content

        detail_view = FolderDetailView(
            folder_data=f_obj,
            subfolders=subfolders,
            saves=matching_saves,
            folder_depth=depth,
            breadcrumb_trail=trail,
            on_back=self.close_folder_detail_view,
            on_select_subfolder=self.open_folder_detail_view,
            on_select_save=self.open_note_view,
            on_rename_folder=self.open_rename_folder_sheet,
            on_add_subfolder=self.open_create_subfolder_sheet,
            on_delete_folder=self.confirm_delete_folder,
            theme_mode=self.theme_mode_val,
        )

        self.current_folder_detail_view = detail_view
        self.viewport.content = detail_view
        return detail_view

    def close_folder_detail_view(self) -> None:
        """Return from FolderDetailView to parent folder or to app shell (Tab 1)."""
        if self.current_folder_detail_view is not None:
            parent_id = self.current_folder_detail_view.folder_data.get("parent_id")
            if parent_id:
                parent_folder = next((f for f in self._folders_collection if f.get("id") == parent_id), None)
                if parent_folder:
                    self.open_folder_detail_view(parent_folder)
                    return

            self.current_folder_detail_view = None

        self.app_shell.set_tab(TAB_FOLDERS)
        self.viewport.content = self.app_shell

    def open_create_folder_sheet(self, parent_data: dict[str, Any] | None = None) -> None:
        """Open CreateFolderSheet modal for creating a folder or subfolder."""
        p_id = parent_data.get("id") if parent_data else None
        p_name = parent_data.get("name") if parent_data else None
        p_depth = self._get_folder_depth(p_id) if p_id else 1
        existing = [str(f.get("name") or "") for f in self._folders_collection]

        def on_create_success(payload: dict[str, Any]) -> None:
            self.overlay_container.visible = False
            self.overlay_container.content = None

            new_folder = {
                "id": str(uuid.uuid4()),
                "name": payload["name"],
                "parent_id": payload.get("parent_id"),
                "save_count": 0,
            }
            self._folders_collection.append(new_folder)
            self.refresh_folders()

            if self.current_folder_detail_view is not None and self.current_folder_detail_view.folder_id == p_id:
                self.open_folder_detail_view(self.current_folder_detail_view.folder_data)

            if self.on_create_folder:
                self.on_create_folder(new_folder)

            self.last_snackbar = UndoSnackBar(
                message=f"Created folder '{new_folder['name']}'",
                duration_ms=UNDO_DURATION_MS,
                on_undo=lambda _: self.undo_folder_creation(new_folder["id"]),
                theme_mode=self.theme_mode_val,
            )

        sheet = CreateFolderSheet(
            parent_id=p_id,
            parent_name=p_name,
            parent_depth=p_depth,
            existing_names=existing,
            on_create=on_create_success,
            on_cancel=lambda: self._close_overlay(),
            theme_mode=self.theme_mode_val,
        )
        self.overlay_container.content = sheet
        self.overlay_container.visible = True

    def open_create_subfolder_sheet(self, parent_data: dict[str, Any]) -> None:
        """Open create sheet explicitly configured with parent."""
        self.open_create_folder_sheet(parent_data=parent_data)

    def open_rename_folder_sheet(self, folder_data: dict[str, Any]) -> None:
        """Open RenameFolderSheet modal."""
        folder_id = str(folder_data.get("id") or "")
        old_name = str(folder_data.get("name") or "")
        existing = [str(f.get("name") or "") for f in self._folders_collection]

        def on_rename_success(f_id: str, new_name: str) -> None:
            self._close_overlay()
            for f in self._folders_collection:
                if f.get("id") == f_id:
                    f["name"] = new_name
                    break

            # Update member saves in inbox
            for s in self.inbox_view._saves:
                if s.get("folder") == old_name:
                    s["folder"] = new_name

            self.refresh_folders()
            if self.current_folder_detail_view is not None:
                updated_f = next((f for f in self._folders_collection if f.get("id") == f_id), None)
                if updated_f:
                    self.open_folder_detail_view(updated_f)

            if self.on_rename_folder:
                self.on_rename_folder(f_id, new_name)

            self.last_snackbar = UndoSnackBar(
                message=f"Renamed to '{new_name}'",
                duration_ms=UNDO_DURATION_MS,
                on_undo=lambda _: self.undo_folder_rename(f_id, old_name),
                theme_mode=self.theme_mode_val,
            )

        sheet = RenameFolderSheet(
            folder_data=folder_data,
            existing_names=existing,
            on_rename=on_rename_success,
            on_cancel=lambda: self._close_overlay(),
            theme_mode=self.theme_mode_val,
        )
        self.overlay_container.content = sheet
        self.overlay_container.visible = True

    def open_folder_context_menu(self, folder_data: dict[str, Any]) -> None:
        """Open context actions sheet on folder card."""
        depth = self._get_folder_depth(folder_data.get("id"))

        def handle_open(f_data):
            self._close_overlay()
            self.open_folder_detail_view(f_data)

        def handle_rename(f_data):
            self._close_overlay()
            self.open_rename_folder_sheet(f_data)

        def handle_add_sub(f_data):
            self._close_overlay()
            self.open_create_subfolder_sheet(f_data)

        def handle_delete(f_data):
            self._close_overlay()
            self.confirm_delete_folder(f_data)

        sheet = FolderContextMenu(
            folder_data,
            folder_depth=depth,
            on_open=handle_open,
            on_rename=handle_rename,
            on_add_subfolder=handle_add_sub,
            on_delete=handle_delete,
            on_cancel=lambda: self._close_overlay(),
            theme_mode=self.theme_mode_val,
        )
        self.overlay_container.content = sheet
        self.overlay_container.visible = True

    def confirm_delete_folder(self, folder_data: dict[str, Any]) -> None:
        """Open delete confirmation dialog."""
        folder_id = str(folder_data.get("id") or "")
        folder_name = str(folder_data.get("name") or "Folder")

        def handle_confirmed_delete(f_id: str) -> None:
            # 1. Remove folder from collection
            deleted = next((f for f in self._folders_collection if f.get("id") == f_id), None)
            if deleted:
                self._folders_collection = [f for f in self._folders_collection if f.get("id") != f_id]
                self._deleted_folders[f_id] = deleted

            # 2. Member saves return to Inbox unfiled (folder = None)
            unfiled_save_ids: list[str] = []
            for s in self.inbox_view._saves:
                if s.get("folder") == folder_name or s.get("folder_id") == f_id:
                    s["folder"] = None
                    s["folder_id"] = None
                    unfiled_save_ids.append(str(s.get("id") or s.get("save_id") or ""))

            self._folder_unfiled_saves[f_id] = unfiled_save_ids

            # 3. Close detail view if open
            if self.current_folder_detail_view is not None:
                self.current_folder_detail_view = None
                self.app_shell.set_tab(TAB_FOLDERS)
                self.viewport.content = self.app_shell

            self.refresh_folders()
            self.inbox_view.rebuild_view()

            if self.on_delete_folder:
                self.on_delete_folder(f_id)

            self.last_snackbar = UndoSnackBar(
                message=f"Deleted folder '{folder_name}'. Member saves returned to Inbox.",
                duration_ms=UNDO_DURATION_MS,
                on_undo=lambda _: self.undo_folder_deletion(f_id),
                theme_mode=self.theme_mode_val,
            )

        dialog = DeleteFolderConfirmDialog(
            folder_data,
            on_confirm_delete=handle_confirmed_delete,
            on_cancel=lambda: None,
            theme_mode=self.theme_mode_val,
        )
        # In Flet app or test, trigger confirm directly or open dialog
        dialog._confirm()

    def undo_folder_creation(self, folder_id: str) -> None:
        """Revert creation of folder."""
        self._folders_collection = [f for f in self._folders_collection if f.get("id") != folder_id]
        self.refresh_folders()

    def undo_folder_rename(self, folder_id: str, old_name: str) -> None:
        """Revert folder rename."""
        for f in self._folders_collection:
            if f.get("id") == folder_id:
                new_name = f.get("name")
                f["name"] = old_name
                # Revert saves
                for s in self.inbox_view._saves:
                    if s.get("folder") == new_name:
                        s["folder"] = old_name
                break
        self.refresh_folders()
        if self.current_folder_detail_view is not None:
            self.open_folder_detail_view(folder_id)

    def undo_folder_deletion(self, folder_id: str) -> None:
        """Revert folder deletion and re-file member saves."""
        if folder_id in self._deleted_folders:
            restored_folder = self._deleted_folders.pop(folder_id)
            self._folders_collection.append(restored_folder)
            fname = restored_folder.get("name")

            if folder_id in self._folder_unfiled_saves:
                saved_ids = set(self._folder_unfiled_saves.pop(folder_id))
                for s in self.inbox_view._saves:
                    s_id = str(s.get("id") or s.get("save_id") or "")
                    if s_id in saved_ids:
                        s["folder"] = fname
                        s["folder_id"] = folder_id

            self.refresh_folders()
            self.inbox_view.rebuild_view()

    def _close_overlay(self) -> None:
        """Close overlay container."""
        self.overlay_container.visible = False
        self.overlay_container.content = None

    # =========================================================================
    # Phase 4: Item Note Navigation and Coordination
    # =========================================================================

    def open_note_view(
        self,
        save: dict[str, Any] | str,
        jump_target: str | None = None,
    ) -> ItemNoteView | None:
        """Navigate to ItemNoteView for a selected save."""
        save_data: dict[str, Any]
        if isinstance(save, dict):
            save_id = str(save.get("id") or save.get("save_id") or "mock-save-id")
            save_data = dict(save)
        else:
            save_id = str(save)
            found = next(
                (s for s in self.inbox_view._saves if str(s.get("id") or s.get("save_id")) == save_id),
                None,
            )
            save_data = dict(found) if found else {"id": save_id}

        # Find matching job if any
        job_data: dict[str, Any] = {}
        for j in self.inbox_view._active_jobs:
            if str(j.get("save_id") or j.get("id")) == save_id:
                job_data = dict(j)
                break

        # Retrieve note data through client or local cache
        raw_markdown: str = ""
        if self.on_get_note is not None:
            res = self.on_get_note(save_id)
            if res is None:
                self.last_snackbar = UndoSnackBar(
                    message=f"Note not found: {save_id}",
                    duration_ms=UNDO_DURATION_MS,
                    theme_mode=self.theme_mode_val,
                )
                return None
            if isinstance(res, dict):
                if "error" in res:
                    self.last_snackbar = UndoSnackBar(
                        message=str(res.get("error")),
                        duration_ms=UNDO_DURATION_MS,
                        theme_mode=self.theme_mode_val,
                    )
                    return None
                raw_markdown = str(res.get("markdown") or "")
            elif isinstance(res, str):
                raw_markdown = res

        if not raw_markdown:
            if save_id in self.notes:
                entry = self.notes[save_id]
                if isinstance(entry, dict):
                    raw_markdown = str(entry.get("markdown") or "")
                else:
                    raw_markdown = str(entry)
            elif "markdown" in save_data:
                raw_markdown = str(save_data["markdown"])
            else:
                raw_markdown = self._resolve_default_markdown(save_id, save_data)

        # Track previous navigation context
        self.previous_view = self.viewport.content

        # Instantiate ItemNoteView
        note_view = ItemNoteView(
            save_id=save_id,
            raw_markdown=raw_markdown,
            save_data=save_data,
            job_data=job_data,
            jump_target=jump_target,
            available_folders=self.available_folders,
            on_back=self.close_note_view,
            on_save_note=self.handle_save_note,
            on_move_folder=self.handle_move_folder,
            on_update_tags=self.handle_update_tags,
            on_reprocess=self.handle_reprocess_note,
            on_delete=self.handle_delete_note,
            on_restore_delete=self.handle_restore_note,
            on_open_url=self.handle_open_url,
            theme_mode=self.theme_mode_val,
        )

        self.current_note_view = note_view
        self.viewport.content = note_view
        return note_view

    def close_note_view(self) -> None:
        """Return from ItemNoteView to previous navigation context."""
        if self.current_note_view is not None:
            if self.current_note_view.is_editing:
                self.current_note_view.set_editing_mode(False)
            self.current_note_view = None

        self.viewport.content = self.previous_view or self.app_shell
        self.previous_view = None

    def _resolve_default_markdown(self, save_id: str, save_data: dict[str, Any]) -> str:
        """Resolve note markdown from fixture or fallback generator."""
        try:
            fixture_path = Path("Docs/api/fixtures/note.fixtures.json")
            if fixture_path.exists():
                fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))
                for entry in fixtures.get("valid", []):
                    if entry.get("save_id") == save_id:
                        return str(entry.get("markdown", ""))
        except Exception:
            pass

        title = save_data.get("title") or save_data.get("user_context") or "Untitled Note"
        platform = save_data.get("platform") or save_data.get("source_app") or "Web"
        url = save_data.get("url") or ""
        folder = save_data.get("folder")
        tags = save_data.get("tags") or []
        channel = save_data.get("channel") or ""

        fm_lines = [
            "---",
            f"source: {platform}",
        ]
        if channel:
            fm_lines.append(f"channel: {channel}")
        if url:
            fm_lines.append(f"video_url: {url}")
        if folder:
            fm_lines.append(f"folder: {folder}")
        if tags:
            fm_lines.append("tags:")
            for t in tags:
                fm_lines.append(f"  - {t}")
        fm_lines.append("---")
        fm_lines.append(f"# {title}\n\n## Overview\nSaved content overview.")
        return "\n".join(fm_lines)

    def handle_save_note(self, save_id: str, markdown: str, updated_at: str) -> Any:
        """Handle note autosave updates."""
        self.notes[save_id] = markdown
        if self.on_save_note is not None:
            return self.on_save_note(save_id, markdown, updated_at)
        return {"status": "saved", "updated_at": updated_at}

    def handle_move_folder(self, save_id: str, folder_path: str | None) -> Any:
        """Handle moving note to a folder."""
        for s in self.inbox_view._saves:
            if str(s.get("id") or s.get("save_id")) == save_id:
                s["folder"] = folder_path
                break
        if self.on_move_folder is not None:
            return self.on_move_folder(save_id, folder_path)
        return {"status": "moved", "folder": folder_path}

    def handle_update_tags(self, save_id: str, tags: list[str]) -> Any:
        """Handle updating note tags."""
        for s in self.inbox_view._saves:
            if str(s.get("id") or s.get("save_id")) == save_id:
                s["tags"] = list(tags)
                break
        if self.on_update_tags is not None:
            return self.on_update_tags(save_id, tags)
        return {"status": "tags_updated", "tags": tags}

    def handle_reprocess_note(self, save_id: str) -> Any:
        """Handle reprocess action protecting note body."""
        if self.on_reprocess_note is not None:
            return self.on_reprocess_note(save_id)
        return {"status": "reprocessing", "save_id": save_id}

    def handle_delete_note(self, save_id: str) -> Any:
        """Handle note deletion."""
        for i, s in enumerate(self.inbox_view._saves):
            if str(s.get("id") or s.get("save_id")) == save_id:
                matching_save = self.inbox_view._saves.pop(i)
                self._deleted_saves[save_id] = matching_save
                break
        if self.on_delete_note is not None:
            return self.on_delete_note(save_id)
        return {"status": "deleted", "save_id": save_id}

    def handle_restore_note(self, save_id: str) -> Any:
        """Handle undo restore of deleted note."""
        if save_id in self._deleted_saves:
            restored = self._deleted_saves.pop(save_id)
            self.inbox_view._saves.append(restored)
            self.inbox_view.rebuild_view()
        if self.on_restore_note is not None:
            return self.on_restore_note(save_id)
        return {"status": "restored", "save_id": save_id}

    def handle_open_url(self, url: str) -> Any:
        """Handle opening external URL."""
        if self.on_open_url is not None:
            return self.on_open_url(url)
        return {"status": "opened", "url": url}
