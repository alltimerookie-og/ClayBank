"""Top-level ClayBank Application Coordinator.

Orchestrates navigation lifecycle across Splash -> Onboarding -> AppShell,
binds the AddLinkPasteSheet modal, coordinates Inbox data refreshes, and triggers
UndoSnackBar feedback for review actions.
Integrates ItemNoteView navigation for viewing and editing saved notes.

Derived from Docs/Phases.md Phase 2 & Phase 4, Docs/UIUX.md, and Prototype v2.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable
import flet as ft

from app.shell.app_shell import AppShellLayout
from app.shell.nav import TAB_INBOX
from app.shell.theme import get_palette
from app.ui.snackbar import UndoSnackBar
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

        self._last_snackbar: UndoSnackBar | None = None
        self.is_paste_sheet_open = False
        self.current_note_view: ItemNoteView | None = None
        self.previous_view: ft.Control | None = None
        self._deleted_saves: dict[str, dict[str, Any]] = {}

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
            theme_mode=theme_mode,
        )

        # Build App Shell hosting the Inbox view (4 tabs: Inbox, Folders, Search, Settings)
        self.app_shell = AppShellLayout(
            inbox_view=self.inbox_view,
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
        # 1. Try loading from fixture if save_id matches fixture
        try:
            fixture_path = Path("Docs/api/fixtures/note.fixtures.json")
            if fixture_path.exists():
                fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))
                for entry in fixtures.get("valid", []):
                    if entry.get("save_id") == save_id:
                        return str(entry.get("markdown", ""))
        except Exception:
            pass

        # 2. Generate structured frontmatter from save data
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
