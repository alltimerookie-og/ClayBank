"""Three-step Onboarding View for ClayBank.

Presents a skip-friendly, 3-screen walkthrough covering capture, enrichment,
and semantic organization before routing into the Inbox shell.

Derived from Docs/Phases.md Phase 2, Docs/UIUX.md §4.2, and Prototype v2.
"""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from app.shell.theme import COVER_GRADIENTS, get_palette
from app.shell.tokens import (
    CARD_RADIUS,
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_H1,
    FONT_SIZE_TITLE,
    MIN_TOUCH_TARGET,
    PILL_RADIUS,
    SPACING_8,
    SPACING_12,
    SPACING_16,
    SPACING_24,
    SPACING_32,
)
from app.ui.card import ClayCard

ONBOARDING_STEPS: tuple[dict[str, Any], ...] = (
    {
        "step": 0,
        "title": "Instant Capture & Paste",
        "description": "Save links from browsers, reels, and feeds with seamless clipboard prefill and quick-tagging.",
        "icon": ft.Icons.LINK_ROUNDED,
        "gradient_key": "g1",
        "badge": "1-Tap Capture",
    },
    {
        "step": 1,
        "title": "Enrichment & Transcription",
        "description": "Automatic on-device speech-to-text, article readability extraction, and clean key takeaway synthesis.",
        "icon": ft.Icons.GRAPHIC_EQ_ROUNDED,
        "gradient_key": "g2",
        "badge": "Whisper & Readability",
    },
    {
        "step": 2,
        "title": "Local AI & Semantic Search",
        "description": "Intelligent folder recommendations with 1-tap accept, citation jumps, and privacy-first local search.",
        "icon": ft.Icons.AUTO_AWESOME_ROUNDED,
        "gradient_key": "g3",
        "badge": "Folders & Ask",
    },
)


class OnboardingView(ft.Container):
    """Single-view 3-step carousel for onboarding without authentication screens."""

    def __init__(
        self,
        *,
        on_finish: Callable[[], None] | None = None,
        on_skip: Callable[[], None] | None = None,
        on_persist_preference: Callable[[str, bool], None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.on_finish = on_finish
        self.on_skip = on_skip
        self.on_persist_preference = on_persist_preference
        self.current_step = 0
        self.theme_mode_val = theme_mode

        palette = get_palette(theme_mode)

        # Header with permanent Skip action
        self.skip_button = ft.TextButton(
            "Skip",
            style=ft.ButtonStyle(
                color=palette["muted"],
            ),
            on_click=lambda _: self.skip(),
        )

        header_row = ft.Row(
            controls=[
                ft.Container(expand=True),
                self.skip_button,
            ],
            alignment=ft.MainAxisAlignment.END,
        )

        # Demo card content elements
        self.step_icon = ft.Icon(
            icon=ONBOARDING_STEPS[0]["icon"],
            size=48.0,
            color=palette["accent_fg"],
        )

        self.step_badge_text = ft.Text(
            value=ONBOARDING_STEPS[0]["badge"],
            size=12.0,
            weight=ft.FontWeight.W_600,
            color=palette["accent_ink"],
            font_family=FONT_FAMILY_UI,
        )

        self.step_badge_container = ft.Container(
            content=self.step_badge_text,
            bgcolor=palette["accent_bg"],
            padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=4.0),
            border_radius=ft.BorderRadius.all(PILL_RADIUS),
        )

        self.step_title = ft.Text(
            value=ONBOARDING_STEPS[0]["title"],
            size=FONT_SIZE_H1,
            weight=ft.FontWeight.W_700,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
            text_align=ft.TextAlign.CENTER,
        )

        self.step_description = ft.Text(
            value=ONBOARDING_STEPS[0]["description"],
            size=FONT_SIZE_BODY,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
            text_align=ft.TextAlign.CENTER,
        )

        # Demonstration card
        g1 = COVER_GRADIENTS["g1"]
        self.icon_box = ft.Container(
            content=self.step_icon,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=[g1[0], g1[1]],
            ),
            border_radius=ft.BorderRadius.all(CARD_RADIUS),
            width=80.0,
            height=80.0,
            alignment=ft.Alignment(0, 0),
        )

        self.demo_card = ClayCard(
            content=ft.Column(
                controls=[
                    self.step_badge_container,
                    self.icon_box,
                    self.step_title,
                    self.step_description,
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=SPACING_16,
            ),
            padding=SPACING_24,
            theme_mode=theme_mode,
        )

        # Progress indicators (dots)
        self.indicator_dots = [
            ft.Container(
                width=24.0 if i == 0 else 8.0,
                height=8.0,
                border_radius=ft.BorderRadius.all(4.0),
                bgcolor=palette["accent"] if i == 0 else palette["line"],
            )
            for i in range(len(ONBOARDING_STEPS))
        ]

        self.indicators_row = ft.Row(
            controls=self.indicator_dots,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=SPACING_8,
        )

        # Navigation controls (Back and Next/Get Started)
        self.back_button = ft.TextButton(
            "Back",
            style=ft.ButtonStyle(color=palette["muted"]),
            visible=False,  # Hidden on step 0
            on_click=lambda _: self.previous_step(),
        )

        self.next_button = ft.FilledButton(
            "Next",
            style=ft.ButtonStyle(
                bgcolor=palette["accent"],
                color=palette["accent_fg"],
                padding=ft.Padding.symmetric(horizontal=SPACING_24, vertical=SPACING_12),
            ),
            on_click=lambda _: self.next_step(),
        )

        bottom_controls = ft.Row(
            controls=[
                self.back_button,
                ft.Container(expand=True),
                self.next_button,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        layout_column = ft.Column(
            controls=[
                header_row,
                ft.Container(height=SPACING_16),
                ft.Container(
                    content=self.demo_card,
                    expand=True,
                    alignment=ft.Alignment(0, 0),
                ),
                ft.Container(height=SPACING_16),
                self.indicators_row,
                ft.Container(height=SPACING_24),
                bottom_controls,
            ],
            expand=True,
            spacing=0,
        )

        super().__init__(
            content=layout_column,
            bgcolor=palette["background"],
            padding=ft.Padding.all(SPACING_24),
            expand=True,
        )

    def update_view(self) -> None:
        """Render controls matching current step state."""
        step_data = ONBOARDING_STEPS[self.current_step]
        palette = get_palette(self.theme_mode_val)

        # Update card content
        self.step_icon.icon = step_data["icon"]
        self.step_badge_text.value = step_data["badge"]
        self.step_title.value = step_data["title"]
        self.step_description.value = step_data["description"]

        # Update gradient box
        grad_tuple = COVER_GRADIENTS[step_data["gradient_key"]]
        self.icon_box.gradient = ft.LinearGradient(
            begin=ft.Alignment(-1, -1),
            end=ft.Alignment(1, 1),
            colors=[grad_tuple[0], grad_tuple[1]],
        )

        # Update step indicators
        for i, dot in enumerate(self.indicator_dots):
            if i == self.current_step:
                dot.width = 24.0
                dot.bgcolor = palette["accent"]
            else:
                dot.width = 8.0
                dot.bgcolor = palette["line"]

        # Back button hidden on step 0
        self.back_button.visible = self.current_step > 0

        # Next button changes text to "Get Started" on final step
        if self.current_step == len(ONBOARDING_STEPS) - 1:
            self.next_button.content = "Get Started"
        else:
            self.next_button.content = "Next"

    def next_step(self) -> None:
        """Advance to next step or complete onboarding on last step."""
        if self.current_step < len(ONBOARDING_STEPS) - 1:
            self.current_step += 1
            self.update_view()
        else:
            self.complete()

    def previous_step(self) -> None:
        """Return to previous step."""
        if self.current_step > 0:
            self.current_step -= 1
            self.update_view()

    def complete(self) -> None:
        """Mark onboarding complete, persist preference, and invoke finish callback."""
        if self.on_persist_preference is not None:
            self.on_persist_preference("has_seen_onboarding", True)
        if self.on_finish is not None:
            self.on_finish()

    def skip(self) -> None:
        """Skip onboarding directly into the inbox and persist preference."""
        if self.on_persist_preference is not None:
            self.on_persist_preference("has_seen_onboarding", True)
        if self.on_skip is not None:
            self.on_skip()
        elif self.on_finish is not None:
            self.on_finish()
