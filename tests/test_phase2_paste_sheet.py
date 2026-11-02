"""Unit tests for P2-04: Add Link Paste Sheet."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import pytest

from app.views.paste_sheet import AddLinkPasteSheet, is_valid_url

FIXTURES_PATH = Path("Docs/api/fixtures")


def test_url_validation_helper() -> None:
    """Verify URL validation recognizes valid and invalid HTTP/HTTPS URLs."""
    assert is_valid_url("https://example.com") is True
    assert is_valid_url("https://www.instagram.com/reel/Cx9abc/") is True
    assert is_valid_url("http://localhost:8000/test") is True

    assert is_valid_url("not a url") is False
    assert is_valid_url("ftp://example.com") is False
    assert is_valid_url("") is False


def test_paste_sheet_empty_clipboard() -> None:
    """Verify paste sheet when clipboard is empty."""
    sheet = AddLinkPasteSheet(clipboard_reader=lambda: None)
    assert sheet.url_field.value is None or sheet.url_field.value == ""
    assert sheet.clipboard_banner.visible is False


def test_paste_sheet_clipboard_prefill() -> None:
    """Verify paste sheet prefills valid URL from foreground clipboard."""
    clip_url = "https://www.instagram.com/reel/Cx9abc/"
    sheet = AddLinkPasteSheet(clipboard_reader=lambda: clip_url)

    assert sheet.url_field.value == clip_url
    assert sheet.clipboard_banner.visible is True
    assert "Cx9abc" in sheet.clipboard_banner_text.value


def test_paste_sheet_clipboard_ignores_invalid_text() -> None:
    """Verify non-URL clipboard text is not prefilled."""
    sheet = AddLinkPasteSheet(clipboard_reader=lambda: "Just a random shopping list")
    assert sheet.url_field.value is None or sheet.url_field.value == ""
    assert sheet.clipboard_banner.visible is False


def test_paste_sheet_clear_action() -> None:
    """Verify clear action resets text, error text, and clipboard banner."""
    sheet = AddLinkPasteSheet(clipboard_reader=lambda: "https://example.com")
    assert sheet.url_field.value == "https://example.com"

    sheet.clear_url()
    assert sheet.url_field.value == ""
    assert sheet.url_field.error is None
    assert sheet.clipboard_banner.visible is False


def test_paste_sheet_tag_toggling() -> None:
    """Verify selecting quick tags updates selected_tags set."""
    sheet = AddLinkPasteSheet()
    assert sheet.selected_tags == set()

    sheet.toggle_tag("ai")
    assert "ai" in sheet.selected_tags

    sheet.toggle_tag("recipe")
    assert sheet.selected_tags == {"ai", "recipe"}

    # Toggle off
    sheet.toggle_tag("ai")
    assert sheet.selected_tags == {"recipe"}


def test_paste_sheet_validation_errors() -> None:
    """Verify empty or invalid URLs trigger validation errors."""
    submitted = False

    def on_sub(payload: dict[str, Any]) -> None:
        nonlocal submitted
        submitted = True

    sheet = AddLinkPasteSheet(on_submit=on_sub)

    # Empty URL
    sheet.url_field.value = ""
    sheet.submit()
    assert sheet.url_field.error == "URL is required"
    assert not submitted

    # Invalid URL
    sheet.url_field.value = "ftp://invalid-domain"
    sheet.submit()
    assert sheet.url_field.error == "Please enter a valid HTTP or HTTPS URL"
    assert not submitted


def test_paste_sheet_successful_submission() -> None:
    """Verify valid submission matches save-capture schema fixture and invokes callbacks."""
    # Load sample from save-capture fixture
    capture_fixture = json.loads((FIXTURES_PATH / "save-capture.fixtures.json").read_text(encoding="utf-8"))
    valid_sample = capture_fixture["valid"][0]

    submitted_payload: dict[str, Any] = {}
    success_delivered: dict[str, Any] = {}

    def on_sub(payload: dict[str, Any]) -> dict[str, Any]:
        nonlocal submitted_payload
        submitted_payload = payload
        return {"id": "save-001", "url": payload["url"], "status": "queued"}

    def on_succ(data: dict[str, Any]) -> None:
        nonlocal success_delivered
        success_delivered = data

    sheet = AddLinkPasteSheet(on_submit=on_sub, on_success=on_succ)
    sheet.url_field.value = valid_sample["url"]
    sheet.context_field.value = valid_sample["user_context"]
    sheet.submit()

    assert submitted_payload["url"] == valid_sample["url"]
    assert submitted_payload["user_context"] == valid_sample["user_context"]
    assert submitted_payload["force"] is False
    assert success_delivered["id"] == "save-001"


def test_paste_sheet_duplicate_409_state() -> None:
    """Verify duplicate 409 already_saved response renders feedback state."""
    def on_sub(payload: dict[str, Any]) -> dict[str, Any]:
        return {"error": "already_saved", "existing_id": "018f4c1a-0000-7de6-9c8e-000000000001"}

    sheet = AddLinkPasteSheet(on_submit=on_sub)
    sheet.url_field.value = "https://example.com/duplicate"
    sheet.submit()

    assert sheet.is_duplicate is True
    assert sheet.feedback_text.visible is True
    assert "Already saved" in sheet.feedback_text.value


def test_paste_sheet_api_error_feedback() -> None:
    """Verify backend exception is displayed in feedback label."""
    def on_sub(payload: dict[str, Any]) -> None:
        raise RuntimeError("Connection timed out to ClayBank server")

    sheet = AddLinkPasteSheet(on_submit=on_sub)
    sheet.url_field.value = "https://example.com/timeout"
    sheet.submit()

    assert sheet.feedback_text.visible is True
    assert "Connection timed out" in sheet.feedback_text.value


def test_paste_sheet_cancel_callback() -> None:
    """Verify cancel button invokes on_cancel callback."""
    cancelled = False

    def on_canc() -> None:
        nonlocal cancelled
        cancelled = True

    sheet = AddLinkPasteSheet(on_cancel=on_canc)
    sheet.cancel()
    assert cancelled

