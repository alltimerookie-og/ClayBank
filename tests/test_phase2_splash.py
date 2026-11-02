"""Unit tests for P2-02: Warm-up Splash View."""

from __future__ import annotations

import flet as ft
import pytest

from app.shell.theme import COVER_GRADIENTS
from app.views.splash_view import SPLASH_STAGES, SplashView


def test_splash_view_composition() -> None:
    """Verify splash view elements: brand mark, wordmark, and cover gradient."""
    splash = SplashView()

    assert splash.brand_icon.icon == ft.Icons.FOLDER_ROUNDED
    assert splash.brand_icon.size == 64.0
    assert splash.wordmark.value == "ClayBank"
    assert splash.progress_bar.value == 0.0
    assert splash.status_label.value == SPLASH_STAGES[0]

    # Verify background gradient uses COVER_GRADIENTS['g1']
    assert isinstance(splash.gradient, ft.LinearGradient)
    g1 = COVER_GRADIENTS["g1"]
    assert splash.gradient.colors == [g1[0], g1[1]]


def test_splash_view_stage_advancement() -> None:
    """Verify progressing through the 3 local readiness stages."""
    splash = SplashView()

    # Stage 0: Local database readiness
    splash.advance_stage(0)
    assert splash.current_stage_index == 0
    assert splash.status_label.value == SPLASH_STAGES[0]
    assert splash.progress_bar.value == 0.33

    # Stage 1: Vector index readiness
    splash.advance_stage(1)
    assert splash.current_stage_index == 1
    assert splash.status_label.value == SPLASH_STAGES[1]
    assert splash.progress_bar.value == 0.67

    # Stage 2: Cached state readiness
    splash.advance_stage(2)
    assert splash.current_stage_index == 2
    assert splash.status_label.value == SPLASH_STAGES[2]
    assert splash.progress_bar.value == 1.0


def test_splash_view_invalid_stage() -> None:
    """Verify out-of-range stage index raises ValueError."""
    splash = SplashView()
    with pytest.raises(ValueError):
        splash.advance_stage(-1)
    with pytest.raises(ValueError):
        splash.advance_stage(3)


def test_splash_view_completion_callback_routes_onboarding() -> None:
    """Verify completion callback delivers has_seen_onboarding flag correctly."""
    callback_delivered: list[bool] = []

    def on_done(seen: bool) -> None:
        callback_delivered.append(seen)

    # When onboarding not seen yet
    splash = SplashView(on_complete=on_done, has_seen_onboarding=False)
    splash.finish_warmup()
    assert splash.is_finished is True
    assert splash.progress_bar.value == 1.0
    assert callback_delivered == [False]

    # When onboarding already seen
    callback_delivered.clear()
    splash_returning = SplashView(on_complete=on_done, has_seen_onboarding=True)
    splash_returning.finish_warmup()
    assert callback_delivered == [True]
