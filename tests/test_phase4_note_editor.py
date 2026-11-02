"""Tests for Phase 4 Cycle 4.5: Flet Note Editor (ADR 0005, UIUX.md §6)."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock
import pytest
import flet as ft

from app.api_client import ApiResult, ClayBankClient
from app.note.editor import NoteEditorModal, open_note_editor, strip_frontmatter
from app.shell.state import build_state


# ==============================================================================
# Helper Unit Tests
# ==============================================================================

def test_strip_frontmatter() -> None:
    raw = """---
source: youtube
channel: Tech
---
# Main Heading
Body text paragraph.
"""
    body = strip_frontmatter(raw)
    assert body.startswith("# Main Heading")
    assert "source: youtube" not in body
    assert "Body text paragraph." in body


def test_strip_frontmatter_no_frontmatter() -> None:
    raw = "# Just Title\n\nNo frontmatter."
    assert strip_frontmatter(raw) == raw


def test_strip_frontmatter_empty() -> None:
    assert strip_frontmatter("") == ""


# ==============================================================================
# ApiClient Unit Tests
# ==============================================================================

@pytest.mark.anyio
async def test_api_client_put_note_and_reprocess() -> None:
    client = ClayBankClient(base_url="http://fake", dev_token="tok", device_id="dev-1")

    recorded_calls: list[dict[str, Any]] = []

    class MockHttpxClient:
        async def request(self, method: str, url: str, **kwargs: Any) -> Any:
            recorded_calls.append({"method": method, "url": url, **kwargs})

            class FakeResponse:
                status_code = 200

                def json(self) -> dict[str, Any]:
                    return {
                        "data": {
                            "save_id": "test-save-id",
                            "markdown": kwargs.get("json", {}).get("markdown"),
                            "updated_at": "2026-03-02T12:00:00Z",
                        }
                    }

            return FakeResponse()

    client._client = MockHttpxClient()  # type: ignore[assignment]

    # Test put_note
    res_put = await client.put_note("save-123", "# New Note", "2026-03-02T10:00:00Z")
    assert res_put.ok is True
    assert len(recorded_calls) == 1
    assert recorded_calls[0]["method"] == "PUT"
    assert "/saves/save-123/note" in recorded_calls[0]["url"]
    assert recorded_calls[0]["json"] == {"markdown": "# New Note", "updated_at": "2026-03-02T10:00:00Z"}

    # Test reprocess
    res_rep = await client.reprocess("save-123", from_stage="analyzing")
    assert res_rep.ok is True
    assert len(recorded_calls) == 2
    assert recorded_calls[1]["method"] == "POST"
    assert "/saves/save-123/reprocess" in recorded_calls[1]["url"]
    assert recorded_calls[1]["params"] == {"from": "analyzing"}


# ==============================================================================
# NoteEditorModal UI State Tests
# ==============================================================================

class FakePage:
    """Mock Flet page for testing widget state transitions without browser window."""

    def __init__(self) -> None:
        self.dialogs: list[ft.AlertDialog] = []
        self.overlay: list[Any] = []
        self.tasks: list[Any] = []
        self.launched_urls: list[str] = []

    def show_dialog(self, dlg: ft.AlertDialog) -> None:
        self.dialogs.append(dlg)

    def pop_dialog(self) -> None:
        if self.dialogs:
            self.dialogs.pop()

    def update(self) -> None:
        pass

    def run_task(self, coro_fn: Any, *args: Any, **kwargs: Any) -> None:
        self.tasks.append((coro_fn, args, kwargs))

    def launch_url(self, url: str) -> None:
        self.launched_urls.append(url)


def test_note_editor_initialization_and_mode_toggle() -> None:
    page = FakePage()
    state = build_state("http://test", "tok", "dev-1")
    save = {"id": "save-1", "title": "Test Title", "url": "https://example.com/v"}

    modal = NoteEditorModal(page, state, save)  # type: ignore[arg-type]
    modal.show()

    assert len(page.dialogs) == 1
    assert modal.title_text.value == "Test Title"
    assert not modal.is_editing
    assert not modal.save_btn.visible
    assert not modal.toolbar_chips.visible

    # Toggle to edit mode
    modal._toggle_mode()
    assert modal.is_editing
    assert modal.save_btn.visible
    assert modal.toolbar_chips.visible
    assert modal.edit_toggle_btn.text == "Preview"

    # Insert markdown snippet
    modal.edit_field.value = "Start text"
    modal._insert_text("\n## Subtitle")
    assert modal.edit_field.value == "Start text\n## Subtitle"

    # Toggle back to preview mode
    modal._toggle_mode()
    assert not modal.is_editing
    assert not modal.save_btn.visible


@pytest.mark.anyio
async def test_note_editor_load_save_success() -> None:
    page = FakePage()
    state = build_state("http://test", "tok", "dev-1")

    # Mock read_save
    save_data = {
        "id": "save-42",
        "title": "Loaded Save",
        "url": "https://youtube.com/watch?v=123",
        "platform": "youtube",
        "kind": "video",
    }
    note_data = {
        "save_id": "save-42",
        "markdown": "---\nsource: youtube\nchannel: Tech Channel\n---\n# Loaded Save\n\n## Overview\nNote overview.",
        "frontmatter": {
            "source": "youtube",
            "channel": "Tech Channel",
            "duration": 180,
            "folder": "Tech/AI",
            "tags": ["ai", "python"],
        },
        "updated_at": "2026-03-02T12:00:00Z",
    }
    job_data = {"state": "ready"}

    async def fake_read_save(save_id: str) -> ApiResult:
        return ApiResult(ok=True, status=200, data={"save": save_data, "note": note_data, "job": job_data})

    state.client.read_save = fake_read_save  # type: ignore[assignment]

    modal = NoteEditorModal(page, state, save_data)  # type: ignore[arg-type]
    await modal._load_save()

    assert modal.is_loading is False
    assert modal.server_updated_at == "2026-03-02T12:00:00Z"
    assert modal.edit_field.value == note_data["markdown"]
    assert modal.preview_markdown.value == "# Loaded Save\n\n## Overview\nNote overview."
    assert modal.banner_error is None


@pytest.mark.anyio
async def test_note_editor_save_note_success() -> None:
    page = FakePage()
    state = build_state("http://test", "tok", "dev-1")
    save = {"id": "save-1", "title": "Save Title"}

    saved_payloads: list[dict[str, Any]] = []

    async def fake_put_note(save_id: str, markdown: str, updated_at: str) -> ApiResult:
        saved_payloads.append({"save_id": save_id, "markdown": markdown, "updated_at": updated_at})
        return ApiResult(
            ok=True,
            status=200,
            data={
                "save_id": save_id,
                "markdown": markdown,
                "frontmatter": {"source": "web"},
                "updated_at": "2026-03-02T14:00:00Z",
            },
        )

    state.client.put_note = fake_put_note  # type: ignore[assignment]

    modal = NoteEditorModal(page, state, save)  # type: ignore[arg-type]
    modal.server_updated_at = "2026-03-02T10:00:00Z"
    modal.is_editing = True
    modal.edit_field.value = "# Updated Note Content"

    await modal._save_note()

    assert len(saved_payloads) == 1
    assert saved_payloads[0]["markdown"] == "# Updated Note Content"
    assert saved_payloads[0]["updated_at"] == "2026-03-02T10:00:00Z"
    assert not modal.is_editing
    assert modal.server_updated_at == "2026-03-02T14:00:00Z"
    assert modal.banner_error is None
    assert len(page.overlay) == 1  # SnackBar added


@pytest.mark.anyio
async def test_note_editor_save_note_optimistic_conflict_409() -> None:
    page = FakePage()
    state = build_state("http://test", "tok", "dev-1")
    save = {"id": "save-1", "title": "Save Title"}

    async def fake_put_note(save_id: str, markdown: str, updated_at: str) -> ApiResult:
        from app.api_client import ApiError
        return ApiResult(
            ok=False,
            status=409,
            error=ApiError(code="conflict", message="Note modified on server"),
        )

    state.client.put_note = fake_put_note  # type: ignore[assignment]

    modal = NoteEditorModal(page, state, save)  # type: ignore[arg-type]
    modal.server_updated_at = "2026-03-02T10:00:00Z"
    modal.is_editing = True
    modal.edit_field.value = "# User Conflicted Edits"

    await modal._save_note()

    assert modal.is_editing  # Stays in edit mode so edits are not lost
    assert modal.banner_warn is not None
    assert "Conflict (409)" in modal.banner_warn
