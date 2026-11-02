"""Theme token module for ClayBank.

Provides canonical color palette tokens and cover gradient tints
derived from Docs/Design.md and Prototype v2.
"""

from __future__ import annotations

import flet as ft

# Exact light mode color palette from Docs/Design.md and prototype CSS.
LIGHT_PALETTE: dict[str, str] = {
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

# Cover-gradient tints (thumbnails, splash, folder collages).
COVER_GRADIENTS: dict[str, tuple[str, str]] = {
    "g1": ("#E9A27F", "#B5532F"),
    "g2": ("#8FB5A6", "#3F7766"),
    "g3": ("#9DB0D6", "#4A5F97"),
    "g4": ("#D6B36A", "#9A7424"),
}

# Exact dark mode color palette from Docs/Design.md and prototype CSS.
DARK_PALETTE: dict[str, str] = {
    "background": "#1C1B19",
    "card": "#262421",
    "ink": "#F2EFE8",
    "muted": "#A8A398",
    "line": "#3A3732",
    "accent": "#E08A64",
    "accent_fg": "#1F1E1D",
    "accent_bg": "#3A2A22",
    "accent_ink": "#F0B79C",
    "ok": "#1F3A31",
    "ok_ink": "#9FD3BF",
    "chip": "#2F2D29",
    "chip_ink": "#CFCABF",
    "page": "#121110",
}


def get_palette(theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT) -> dict[str, str]:
    """Return the palette dictionary for the given theme mode."""
    mode_str = theme_mode.value if isinstance(theme_mode, ft.ThemeMode) else str(theme_mode).lower()
    if mode_str in ("dark", "d"):
        return DARK_PALETTE
    return LIGHT_PALETTE


def build_color_scheme(theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT) -> ft.ColorScheme:
    """Build a Flet ColorScheme aligned with ClayBank design tokens."""
    palette = get_palette(theme_mode)
    return ft.ColorScheme(
        primary=palette["accent"],
        on_primary=palette["accent_fg"],
        primary_container=palette["accent_bg"],
        on_primary_container=palette["accent_ink"],
        surface=palette["card"],
        on_surface=palette["ink"],
        on_surface_variant=palette["muted"],
        outline=palette["line"],
        surface_container=palette["background"],
    )


def get_flet_theme(theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT) -> ft.Theme:
    """Construct an ft.Theme object configured with ClayBank design tokens."""
    return ft.Theme(
        color_scheme=build_color_scheme(theme_mode),
        font_family="system-ui",
    )


