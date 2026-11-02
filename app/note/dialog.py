"""Note dialog — delegates to Phase 4 interactive NoteEditorModal."""
from __future__ import annotations

import flet as ft

from app.note.editor import open_note_editor, NoteEditorModal
from app.shell.components import kind_chip, platform_chip, processing_chip
from app.shell.theme import Tokens as T


async def open_note_dialog(page: ft.Page, state, save: dict) -> None:
    """Launch the Phase 4 interactive Note Editor & Viewer modal."""
    open_note_editor(page, state, save)


def dlg_tile(save: dict, job_state: str | None) -> ft.Column:
    url = save.get("url", "?")
    return ft.Column([
        ft.Text(save.get("title") or url, weight=ft.FontWeight.BOLD, color=T.INK),
        ft.Text(url, size=11, color=T.MUTED, selectable=True),
        ft.Text(f'{save.get("platform", "?")} · {save.get("captured_at", "")}', size=12, color=T.MUTED),
        ft.Row([
            platform_chip(str(save.get("platform", ""))),
            kind_chip(str(save.get("kind", "unknown"))),
            processing_chip(job_state),
        ], spacing=6, wrap=True),
    ], spacing=4, tight=True)
