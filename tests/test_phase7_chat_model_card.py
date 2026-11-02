"""Tests for ChatModelCard (P7-02 deliverable).

Validates Chat model selection (Cloud | Local), mandatory explanatory copy,
local model picker (MiniCPM5-2B · 1.56 GB vs Qwen3-1.7B · 1.1 GB),
execution hints, setup/download progress states, and callback behaviors.
"""

from __future__ import annotations

import flet as ft
import pytest

from app.views.settings.chat_model_card import (
    EXPLANATORY_COPY,
    MODEL_LABELS,
    MODEL_MINICPM,
    MODEL_QWEN,
    RUNNING_SLOWER_HINT,
    SETTING_UP_HINT,
    ChatModelCard,
)


class TestChatModelCard:
    """Test suite for ChatModelCard component."""

    def test_default_cloud_state(self) -> None:
        """Verify default construction is Cloud mode with local sections hidden."""
        card = ChatModelCard()
        assert card._chat_model == "cloud"
        assert card.title_text.value == "Chat model"
        assert card.copy_text.value == EXPLANATORY_COPY
        # Local picker and hint must be hidden in Cloud mode
        assert card.local_picker_section.visible is False
        assert card.hint_text.visible is False
        assert card.setup_section.visible is False

    def test_explanatory_copy_locked(self) -> None:
        """Verify exact locked copy is present."""
        card = ChatModelCard()
        assert card.copy_text.value == "Notes are always generated in the cloud. Chat can run on this device."

    def test_model_names_and_labels(self) -> None:
        """Verify exact model names and memory sizes."""
        assert MODEL_LABELS[MODEL_MINICPM] == "MiniCPM5-2B · 1.56 GB"
        assert MODEL_LABELS[MODEL_QWEN] == "Qwen3-1.7B · 1.1 GB"

    def test_switch_to_local_reveals_picker(self) -> None:
        """Switching to Local mode makes local model picker visible."""
        card = ChatModelCard(chat_model="cloud")
        assert card.local_picker_section.visible is False

        card.set_chat_model("local")
        assert card._chat_model == "local"
        assert card.local_picker_section.visible is True

    def test_engine_change_callback(self) -> None:
        """Clicking Local/Cloud dispatches on_model_change."""
        dispatched: list[str] = []

        def handle_change(engine: str) -> None:
            dispatched.append(engine)

        card = ChatModelCard(chat_model="cloud", on_model_change=handle_change)
        # Click local button
        assert card.local_btn.on_click is not None
        card.local_btn.on_click(None)

        assert dispatched == ["local"]
        assert card._chat_model == "local"

    def test_local_model_pick_callback(self) -> None:
        """Selecting another local model dispatches on_local_model_pick."""
        picked: list[str] = []

        def handle_pick(model_id: str) -> None:
            picked.append(model_id)

        card = ChatModelCard(
            chat_model="local",
            local_model_id=MODEL_MINICPM,
            on_local_model_pick=handle_pick,
        )
        assert card.chip_qwen.on_click is not None
        card.chip_qwen.on_click(None)

        assert picked == [MODEL_QWEN]
        assert card._local_model_id == MODEL_QWEN

    def test_no_automatic_download_on_render(self) -> None:
        """No download setup callback should fire simply by rendering."""
        setup_calls: list[str] = []

        def handle_setup(m: str) -> None:
            setup_calls.append(m)

        _ = ChatModelCard(
            chat_model="local",
            is_local_ready=False,
            on_request_setup=handle_setup,
        )
        # Must be empty
        assert len(setup_calls) == 0

    def test_explicit_setup_button_triggers_callback(self) -> None:
        """User tapping Download model triggers on_request_setup."""
        setup_calls: list[str] = []

        def handle_setup(m: str) -> None:
            setup_calls.append(m)

        card = ChatModelCard(
            chat_model="local",
            local_model_id=MODEL_MINICPM,
            is_local_ready=False,
            is_downloading=False,
            on_request_setup=handle_setup,
        )
        assert card.setup_button.visible is True
        assert card.setup_button.on_click is not None
        card.setup_button.on_click(None)

        assert setup_calls == [MODEL_MINICPM]

    def test_download_progress_state(self) -> None:
        """Active download shows progress bar and setting up hint."""
        card = ChatModelCard(
            chat_model="local",
            is_downloading=True,
            download_progress=0.45,
        )
        assert card.progress_bar.visible is True
        assert card.progress_bar.value == 0.45
        assert card.setup_label.value == SETTING_UP_HINT
        assert card.hint_text.visible is False

    def test_running_slower_hint_visibility(self) -> None:
        """'running on device · slower' only visible when local is ready and not downloading."""
        # Cloud: not visible
        c1 = ChatModelCard(chat_model="cloud", is_local_ready=True)
        assert c1.hint_text.visible is False

        # Local not ready: not visible
        c2 = ChatModelCard(chat_model="local", is_local_ready=False)
        assert c2.hint_text.visible is False

        # Local ready: visible
        c3 = ChatModelCard(chat_model="local", is_local_ready=True, is_downloading=False)
        assert c3.hint_text.visible is True
        assert c3.hint_text.value == RUNNING_SLOWER_HINT

    def test_dynamic_download_state_updates(self) -> None:
        """Test set_download_state transitions."""
        card = ChatModelCard(chat_model="local", is_local_ready=False)
        assert card.setup_button.visible is True

        # Transition to downloading
        card.set_download_state(is_downloading=True, progress=0.75, is_ready=False)
        assert card.progress_bar.visible is True
        assert card.progress_bar.value == 0.75
        assert card.setup_button.visible is False

        # Transition to ready
        card.set_download_state(is_downloading=False, progress=None, is_ready=True)
        assert card.progress_bar.visible is False
        assert card.setup_section.visible is False
        assert card.hint_text.visible is True

    def test_dark_mode_rendering(self) -> None:
        """Verify dark mode styling."""
        card = ChatModelCard(theme_mode=ft.ThemeMode.DARK, chat_model="local")
        assert card.bgcolor is not None
