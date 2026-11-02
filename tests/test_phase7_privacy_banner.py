"""Tests for PrivacyBanner (P7-04 deliverable).

Validates exact copy, non-dismissibility, theme awareness, and layout.
"""

from __future__ import annotations

import flet as ft
import pytest

from app.views.settings.privacy_banner import PRIVACY_BANNER_TEXT, PrivacyBanner


class TestPrivacyBanner:
    """Test suite for PrivacyBanner component."""

    def test_exact_locked_copy(self) -> None:
        """Verify exact copy string from Docs/Design.md §8."""
        assert PRIVACY_BANNER_TEXT == "Privacy: videos are never saved. Cloud AI gets the transcript and metadata only."

    def test_banner_content(self) -> None:
        """Verify banner displays lock icon and disclosure copy."""
        banner = PrivacyBanner()
        assert banner.text_control.value == PRIVACY_BANNER_TEXT
        assert banner.icon_control.icon == ft.Icons.LOCK_OUTLINE_ROUNDED

    def test_non_dismissible(self) -> None:
        """Verify banner has no close/dismiss controls."""
        banner = PrivacyBanner()
        row = banner.content
        assert isinstance(row, ft.Row)
        # Only icon and text controls in the row
        assert len(row.controls) == 2
        assert not any(isinstance(c, ft.IconButton) for c in row.controls)

    def test_dark_mode_rendering(self) -> None:
        """Verify dark mode styling."""
        banner = PrivacyBanner(theme_mode=ft.ThemeMode.DARK)
        assert banner.bgcolor is not None
