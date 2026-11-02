"""Warm-up Splash View for ClayBank.

Displays the ClayBank brand mark, wordmark, cover gradient background,
and a determinate progress bar advancing through 3 local readiness stages.

Derived from Docs/Phases.md Phase 2, Docs/Design.md §3, and Prototype v2.
"""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from app.shell.icons import get_icon
from app.shell.theme import COVER_GRADIENTS, get_palette
from app.shell.tokens import (
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_DISPLAY,
    FONT_SIZE_MUTED,
    SPACING_8,
    SPACING_12,
    SPACING_24,
    SPACING_32,
)

SPLASH_STAGES: tuple[str, ...] = (
    "Verifying local database readiness...",
    "Warming up vector index...",
    "Checking cached state readiness...",
)


class SplashView(ft.Container):
    """Warm-up splash screen with brand folder mark, wordmark, and determinate progress bar.

    Never blocks on network synchronization. Advances through 3 local stages
    before invoking on_complete(has_seen_onboarding).
    """

    def __init__(
        self,
        *,
        on_complete: Callable[[bool], None] | None = None,
        has_seen_onboarding: bool = False,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.on_complete = on_complete
        self.has_seen_onboarding = has_seen_onboarding
        self.current_stage_index = 0
        self.is_finished = False

        # Brand folder icon
        self.brand_icon = ft.Icon(
            icon=ft.Icons.FOLDER_ROUNDED,
            size=64.0,
            color="#FFFFFF",
        )

        # Brand wordmark
        self.wordmark = ft.Text(
            value="ClayBank",
            size=FONT_SIZE_DISPLAY,
            weight=ft.FontWeight.W_800,
            color="#FFFFFF",
            font_family=FONT_FAMILY_UI,
        )

        # Tagline
        self.tagline = ft.Text(
            value="Personal Knowledge Wallet",
            size=FONT_SIZE_BODY,
            weight=ft.FontWeight.W_500,
            color="rgba(255,255,255,0.85)",
            font_family=FONT_FAMILY_UI,
        )

        # Determinate progress bar
        self.progress_bar = ft.ProgressBar(
            value=0.0,
            width=220.0,
            color="#FFFFFF",
            bgcolor="rgba(255, 255, 255, 0.25)",
        )

        # Status stage label
        self.status_label = ft.Text(
            value=SPLASH_STAGES[0],
            size=FONT_SIZE_MUTED,
            color="rgba(255,255,255,0.9)",
            font_family=FONT_FAMILY_UI,
            text_align=ft.TextAlign.CENTER,
        )

        content_column = ft.Column(
            controls=[
                self.brand_icon,
                self.wordmark,
                self.tagline,
                ft.Container(height=SPACING_32),
                self.progress_bar,
                ft.Container(height=SPACING_8),
                self.status_label,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=SPACING_8,
        )

        # Gradient background using COVER_GRADIENTS["g1"] (#E9A27F to #B5532F)
        g1 = COVER_GRADIENTS["g1"]
        gradient = ft.LinearGradient(
            begin=ft.Alignment(0, -1),
            end=ft.Alignment(0, 1),
            colors=[g1[0], g1[1]],
        )

        super().__init__(
            content=content_column,
            alignment=ft.Alignment(0, 0),
            gradient=gradient,
            expand=True,
        )

    def advance_stage(self, stage_idx: int) -> None:
        """Advance progress to a specific local readiness stage (0, 1, 2)."""
        if not (0 <= stage_idx < len(SPLASH_STAGES)):
            raise ValueError(f"stage_idx must be between 0 and {len(SPLASH_STAGES) - 1}")

        self.current_stage_index = stage_idx
        self.status_label.value = SPLASH_STAGES[stage_idx]
        # Stage 0: 33%, Stage 1: 67%, Stage 2: 100%
        self.progress_bar.value = round((stage_idx + 1) / len(SPLASH_STAGES), 2)

    def finish_warmup(self) -> None:
        """Complete warm-up and trigger completion transition."""
        self.is_finished = True
        self.progress_bar.value = 1.0
        self.status_label.value = "Ready"
        if self.on_complete is not None:
            self.on_complete(self.has_seen_onboarding)
