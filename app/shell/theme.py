"""Theme token module for ClayBank.

Provides canonical color palette tokens and cover gradient tints
derived from Docs/Design.md and Prototype v2.
"""

from __future__ import annotations

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

