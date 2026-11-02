"""Test suite for Phase 8 AddLinkPasteSheet Intent and External Capture Support.

Validates initial_url prefilling, source_app attribution (share_target, notification, manual_paste),
bypassing of clipboard readers when initial_url is supplied, and payload conformance.
Derived from Docs/Phases.md Phase 8 and Docs/api/schemas/save-capture.json.
"""

from __future__ import annotations

from typing import Any
import pytest

from app.views.paste_sheet import AddLinkPasteSheet


class TestPasteSheetIntent:
    """Tests for Phase 8 external capture intent prefill and source attribution."""

    def test_initial_url_prefills_field_and_bypasses_clipboard(self) -> None:
        """Verify initial_url is populated and clipboard_reader is NOT called."""
        clipboard_called = False

        def mock_clipboard() -> str:
            nonlocal clipboard_called
            clipboard_called = True
            return "https://clipboard.example.com/item"

        sheet = AddLinkPasteSheet(
            initial_url="https://shared.example.com/article/42",
            source_app="share_target",
            clipboard_reader=mock_clipboard,
        )

        assert sheet.url_field.value == "https://shared.example.com/article/42"
        assert clipboard_called is False
        assert sheet.clipboard_banner.visible is True
        assert "share" in sheet.clipboard_banner_text.value.lower()

    def test_share_target_source_app_in_submission_payload(self) -> None:
        """Verify source_app='share_target' is properly included in submit payload."""
        captured_payload: dict[str, Any] = {}

        def mock_submit(payload: dict[str, Any]) -> dict[str, Any]:
            nonlocal captured_payload
            captured_payload = payload
            return {"id": "save-intent-1", "url": payload["url"], "status": "queued"}

        sheet = AddLinkPasteSheet(
            initial_url="https://youtube.com/watch?v=12345",
            source_app="share_target",
            on_submit=mock_submit,
        )

        sheet.submit()

        assert captured_payload["url"] == "https://youtube.com/watch?v=12345"
        assert captured_payload["source_app"] == "share_target"
        assert captured_payload["force"] is False

    def test_notification_quick_save_source_app_in_submission_payload(self) -> None:
        """Verify source_app='notification' is properly included in submit payload."""
        captured_payload: dict[str, Any] = {}

        def mock_submit(payload: dict[str, Any]) -> dict[str, Any]:
            nonlocal captured_payload
            captured_payload = payload
            return {"id": "save-intent-2", "url": payload["url"], "status": "queued"}

        sheet = AddLinkPasteSheet(
            initial_url="https://news.ycombinator.com/item?id=999",
            source_app="notification",
            on_submit=mock_submit,
        )

        assert "quick-save" in sheet.clipboard_banner_text.value.lower()
        sheet.submit()

        assert captured_payload["url"] == "https://news.ycombinator.com/item?id=999"
        assert captured_payload["source_app"] == "notification"

    def test_empty_initial_url_falls_back_to_clipboard_reader(self) -> None:
        """Verify None or empty initial_url falls back to foreground clipboard detection."""
        sheet = AddLinkPasteSheet(
            initial_url=None,
            clipboard_reader=lambda: "https://from-clipboard.com/recipe",
        )

        assert sheet.url_field.value == "https://from-clipboard.com/recipe"
        assert sheet.clipboard_banner.visible is True
        assert "clipboard" in sheet.clipboard_banner_text.value.lower()

    def test_clear_url_resets_source_app_to_manual_paste(self) -> None:
        """Verify clearing prefilled URL resets source_app to manual_paste."""
        sheet = AddLinkPasteSheet(
            initial_url="https://shared.example.com",
            source_app="share_target",
        )
        assert sheet.source_app == "share_target"

        sheet.clear_url()
        assert sheet.url_field.value == ""
        assert sheet.source_app == "manual_paste"
        assert sheet.clipboard_banner.visible is False

    def test_prefilled_invalid_url_still_validates_on_submit(self) -> None:
        """Verify invalid prefilled URL halts submission with proper error message."""
        submitted = False

        def mock_submit(payload: dict[str, Any]) -> None:
            nonlocal submitted
            submitted = True

        sheet = AddLinkPasteSheet(
            initial_url="not-a-valid-http-url",
            source_app="share_target",
            on_submit=mock_submit,
        )

        sheet.submit()
        assert submitted is False
        assert sheet.url_field.error == "Please enter a valid HTTP or HTTPS URL"
