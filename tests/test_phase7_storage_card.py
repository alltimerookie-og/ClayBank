"""Tests for StorageUsedCard (P7-03 deliverable).

Validates byte formatting, split storage display (Library · Local model),
handling of zero, missing, and invalid values, dynamic updates, and theme modes.
"""

from __future__ import annotations

import flet as ft
import pytest

from app.views.settings.storage_card import (
    StorageUsedCard,
    format_split_storage,
    format_storage_size,
)


class TestStorageCard:
    """Test suite for StorageUsedCard component and formatting utilities."""

    def test_bytes_formatting(self) -> None:
        """Verify byte values below 1 KB."""
        assert format_storage_size(0) == "0 B"
        assert format_storage_size(512) == "512 B"
        assert format_storage_size(1023) == "1023 B"

    def test_kb_formatting(self) -> None:
        """Verify KB values."""
        assert format_storage_size(1024) == "1.0 KB"
        assert format_storage_size(1536) == "1.5 KB"
        assert format_storage_size(50 * 1024) == "50 KB"

    def test_mb_formatting(self) -> None:
        """Verify MB values."""
        assert format_storage_size(1024 * 1024) == "1 MB"
        assert format_storage_size(4 * 1024 * 1024) == "4 MB"
        assert format_storage_size(int(4.5 * 1024 * 1024)) == "4.5 MB"

    def test_gb_formatting(self) -> None:
        """Verify GB values."""
        assert format_storage_size(1024 * 1024 * 1024) == "1 GB"
        assert format_storage_size(int(1.1 * 1024 * 1024 * 1024)) == "1.1 GB"
        assert format_storage_size(int(1.56 * 1024 * 1024 * 1024)) == "1.6 GB"

    def test_exact_prototype_split_example(self) -> None:
        """Verify exact locked example string: 'Library 4 MB · Local model 1.1 GB'."""
        lib_bytes = 4 * 1024 * 1024
        model_bytes = int(1.1 * 1024 * 1024 * 1024)
        formatted = format_split_storage(lib_bytes, model_bytes)
        assert formatted == "Library 4 MB · Local model 1.1 GB"

    def test_zero_and_missing_values(self) -> None:
        """Verify handling of zero and None."""
        assert format_storage_size(None) == "0 B"
        assert format_split_storage(None, None) == "Library 0 B · Local model 0 B"
        assert format_split_storage(0, 0) == "Library 0 B · Local model 0 B"

    def test_invalid_values(self) -> None:
        """Verify negative or invalid values."""
        assert format_storage_size(-100) == "0 B"
        assert format_storage_size("invalid") == "0 B"

    def test_default_card_rendering(self) -> None:
        """Verify card construction with defaults."""
        card = StorageUsedCard()
        assert card.title_text.value == "Storage used"
        assert "Library 4 MB · Local model 1.1 GB" in card.value_text.value

    def test_dynamic_storage_updates(self) -> None:
        """Verify set_storage method updates text."""
        card = StorageUsedCard(library_bytes=0, local_model_bytes=0)
        assert card.value_text.value == "Library 0 B · Local model 0 B"

        card.set_storage(10 * 1024 * 1024, int(1.56 * 1024 * 1024 * 1024))
        assert card.value_text.value == "Library 10 MB · Local model 1.6 GB"

    def test_custom_text_override(self) -> None:
        """Verify custom_display_text and set_custom_text."""
        card = StorageUsedCard(custom_display_text="Library 4 MB · Local model 1.1 GB")
        assert card.value_text.value == "Library 4 MB · Local model 1.1 GB"

        card.set_custom_text("Library 8 MB · Local model 0 B")
        assert card.value_text.value == "Library 8 MB · Local model 0 B"

    def test_dark_mode_rendering(self) -> None:
        """Verify dark mode styling."""
        card = StorageUsedCard(theme_mode=ft.ThemeMode.DARK)
        assert card.bgcolor is not None
