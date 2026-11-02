"""Unit tests for P2-03: Onboarding View."""

from __future__ import annotations

import flet as ft

from app.views.onboarding_view import ONBOARDING_STEPS, OnboardingView


def test_onboarding_initial_step() -> None:
    """Verify onboarding initial state on Step 0."""
    view = OnboardingView()

    assert view.current_step == 0
    assert view.step_title.value == ONBOARDING_STEPS[0]["title"]
    assert view.back_button.visible is False
    assert view.next_button.content == "Next"
    assert view.skip_button.visible is True
    assert len(view.indicator_dots) == 3
    assert view.indicator_dots[0].width == 24.0
    assert view.indicator_dots[1].width == 8.0
    assert view.indicator_dots[2].width == 8.0


def test_onboarding_step_transitions() -> None:
    """Verify advancing through all three steps and returning."""
    view = OnboardingView()

    # Move to Step 1
    view.next_step()
    assert view.current_step == 1
    assert view.step_title.value == ONBOARDING_STEPS[1]["title"]
    assert view.back_button.visible is True
    assert view.next_button.content == "Next"
    assert view.indicator_dots[0].width == 8.0
    assert view.indicator_dots[1].width == 24.0

    # Move to Step 2 (Final)
    view.next_step()
    assert view.current_step == 2
    assert view.step_title.value == ONBOARDING_STEPS[2]["title"]
    assert view.back_button.visible is True
    assert view.next_button.content == "Get Started"
    assert view.indicator_dots[2].width == 24.0

    # Go back to Step 1
    view.previous_step()
    assert view.current_step == 1
    assert view.next_button.content == "Next"

    # Go back to Step 0
    view.previous_step()
    assert view.current_step == 0
    assert view.back_button.visible is False


def test_onboarding_completion_callback() -> None:
    """Verify completion on final step calls finish callback and persists preference."""
    finished = False
    persisted: dict[str, bool] = {}

    def on_finish() -> None:
        nonlocal finished
        finished = True

    def on_persist(key: str, val: bool) -> None:
        persisted[key] = val

    view = OnboardingView(
        on_finish=on_finish,
        on_persist_preference=on_persist,
    )

    view.next_step()  # step 1
    view.next_step()  # step 2
    view.next_step()  # triggers complete()

    assert finished is True
    assert persisted == {"has_seen_onboarding": True}


def test_onboarding_skip_callback() -> None:
    """Verify skip triggers skip callback and persists preference from any step."""
    skipped = False
    persisted: dict[str, bool] = {}

    def on_skip() -> None:
        nonlocal skipped
        skipped = True

    def on_persist(key: str, val: bool) -> None:
        persisted[key] = val

    view = OnboardingView(
        on_skip=on_skip,
        on_persist_preference=on_persist,
    )

    view.skip()
    assert skipped is True
    assert persisted == {"has_seen_onboarding": True}
