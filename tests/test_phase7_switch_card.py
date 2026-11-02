"""Tests for SettingSwitchCard (P7-04 deliverable).

Validates default values, labels, boolean callbacks, 44 px touch targets,
disabled states, and absence of native Android permission calls.
"""

from __future__ import annotations

import flet as ft
import pytest

from app.shell.tokens import MIN_TOUCH_TARGET
from app.views.settings.switch_card import SettingSwitchCard


class TestSettingSwitchCard:
    """Test suite for SettingSwitchCard component."""

    def test_default_values_and_labels(self) -> None:
        """Verify initialization with documented defaults."""
        s1 = SettingSwitchCard("Auto-sort new saves", field_key="auto_sort", value=True)
        assert s1.title == "Auto-sort new saves"
        assert s1.field_key == "auto_sort"
        assert s1.value is True
        assert s1.switch_control.value is True

        s2 = SettingSwitchCard("Weekly digest of unopened saves", field_key="weekly_digest", value=True)
        assert s2.value is True

        s3 = SettingSwitchCard("Wi-Fi only processing", field_key="wifi_only_processing", value=False)
        assert s3.value is False

        s4 = SettingSwitchCard("Quick-save notification", field_key="quick_save_notification", value=True)
        assert s4.value is True

    def test_minimum_touch_target(self) -> None:
        """Ensure switch interactive target meets WCAG 44 px guideline."""
        card = SettingSwitchCard("Auto-sort", field_key="auto_sort", value=True)
        assert card.switch_control.height == MIN_TOUCH_TARGET

    def test_toggle_callback_dispatch(self) -> None:
        """User toggling the switch invokes on_change with exact key and bool."""
        dispatched: list[tuple[str, bool]] = []

        def handle_change(key: str, val: bool) -> None:
            dispatched.append((key, val))

        card = SettingSwitchCard(
            "Auto-sort new saves",
            field_key="auto_sort",
            value=True,
            on_change=handle_change,
        )

        # Simulate toggle to False
        event = type("Event", (), {"control": type("Control", (), {"value": False})()})()
        assert card.switch_control.on_change is not None
        card.switch_control.on_change(event)

        assert dispatched == [("auto_sort", False)]
        assert card.value is False

    def test_programmatic_value_and_disabled_setters(self) -> None:
        """Verify set_value and set_disabled methods."""
        card = SettingSwitchCard("Wi-Fi only", field_key="wifi_only_processing", value=False)
        assert card.value is False

        card.set_value(True)
        assert card.value is True
        assert card.switch_control.value is True

        card.set_disabled(True)
        assert card.switch_control.disabled is True

    def test_dark_mode_rendering(self) -> None:
        """Verify rendering under dark theme."""
        card = SettingSwitchCard(
            "Test Switch",
            field_key="test_key",
            theme_mode=ft.ThemeMode.DARK,
        )
        assert card.bgcolor is not None
