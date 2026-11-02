"""Unit tests for Phase 0 Step 2: Light Theme Tokens Module."""

from __future__ import annotations

import re

from app.shell.theme import COVER_GRADIENTS, LIGHT_PALETTE

EXPECTED_LIGHT_PALETTE: dict[str, str] = {
    "background": "#FAF9F5",
    "card": "#FFFFFF",
    "ink": "#1F1E1D",
    "muted": "#6B6860",
    "line": "#E1DCCF",
    "accent": "#B5532F",
    "accent_fg": "#FFFFFF",
    "accent_bg": "#F6E4DA",
    "accent_ink": "#8A3E22",
    "ok": "#E3F0EA",
    "ok_ink": "#2E5E50",
    "chip": "#EEEBE2",
    "chip_ink": "#4A4842",
    "page": "#EFEBE1",
}

EXPECTED_COVER_GRADIENTS: dict[str, tuple[str, str]] = {
    "g1": ("#E9A27F", "#B5532F"),
    "g2": ("#8FB5A6", "#3F7766"),
    "g3": ("#9DB0D6", "#4A5F97"),
    "g4": ("#D6B36A", "#9A7424"),
}

HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


def test_light_palette_exact_keys() -> None:
    """Verify no unexpected or missing keys in LIGHT_PALETTE."""
    assert set(LIGHT_PALETTE.keys()) == set(EXPECTED_LIGHT_PALETTE.keys())


def test_light_palette_exact_values() -> None:
    """Verify each light palette key maps to the exact documented hex value."""
    for key, expected_value in EXPECTED_LIGHT_PALETTE.items():
        actual_value = LIGHT_PALETTE.get(key)
        assert actual_value == expected_value, (
            f"Key '{key}' expected {expected_value}, got {actual_value}"
        )


def test_light_palette_hex_format() -> None:
    """Verify that all light palette colors are valid 6-character hex strings."""
    for key, value in LIGHT_PALETTE.items():
        assert HEX_COLOR_PATTERN.match(value), (
            f"Value for '{key}' ({value}) is not a valid 6-digit hex color"
        )


def test_cover_gradients_exact_values() -> None:
    """Verify all four cover gradients match documented gradient pairs."""
    assert set(COVER_GRADIENTS.keys()) == set(EXPECTED_COVER_GRADIENTS.keys())
    for key, expected_pair in EXPECTED_COVER_GRADIENTS.items():
        actual_pair = COVER_GRADIENTS.get(key)
        assert actual_pair == expected_pair, (
            f"Gradient '{key}' expected {expected_pair}, got {actual_pair}"
        )


def test_cover_gradients_hex_format() -> None:
    """Verify that all cover gradient colors are valid 6-character hex strings."""
    for key, (start_color, end_color) in COVER_GRADIENTS.items():
        assert HEX_COLOR_PATTERN.match(start_color), (
            f"Gradient '{key}' start color {start_color} is not valid hex"
        )
        assert HEX_COLOR_PATTERN.match(end_color), (
            f"Gradient '{key}' end color {end_color} is not valid hex"
        )


def _srgb_to_linear(channel_val: int) -> float:
    normalized = channel_val / 255.0
    if normalized <= 0.04045:
        return normalized / 12.92
    return ((normalized + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_color: str) -> float:
    cleaned = hex_color.lstrip("#")
    r = int(cleaned[0:2], 16)
    g = int(cleaned[2:4], 16)
    b = int(cleaned[4:6], 16)
    return (
        0.2126 * _srgb_to_linear(r)
        + 0.7152 * _srgb_to_linear(g)
        + 0.0722 * _srgb_to_linear(b)
    )


def _contrast_ratio(hex1: str, hex2: str) -> float:
    l1 = _relative_luminance(hex1)
    l2 = _relative_luminance(hex2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def test_wcag_contrast_ink_against_background() -> None:
    """Verify ink on background meets or exceeds 7:1 ratio (expected ~15.80:1)."""
    ratio = _contrast_ratio(LIGHT_PALETTE["ink"], LIGHT_PALETTE["background"])
    assert ratio >= 7.0, f"Contrast ratio {ratio:.2f}:1 is less than required 7:1"
    assert round(ratio, 2) == 15.80


def test_wcag_contrast_muted_against_background() -> None:
    """Verify muted on background meets or exceeds 4.5:1 ratio (expected ~5.28:1)."""
    ratio = _contrast_ratio(LIGHT_PALETTE["muted"], LIGHT_PALETTE["background"])
    assert ratio >= 4.5, f"Contrast ratio {ratio:.2f}:1 is less than required 4.5:1"
    assert round(ratio, 2) == 5.28


def test_wcag_contrast_accent_ink_against_accent_bg() -> None:
    """Verify accent_ink on accent_bg meets or exceeds 4.5:1 ratio (expected ~6.10:1)."""
    ratio = _contrast_ratio(LIGHT_PALETTE["accent_ink"], LIGHT_PALETTE["accent_bg"])
    assert ratio >= 4.5, f"Contrast ratio {ratio:.2f}:1 is less than required 4.5:1"
    assert round(ratio, 2) == 6.10


