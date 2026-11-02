"""Chat model configuration and local model picker card for ClayBank Settings.

Controls the chat execution engine (Cloud vs Local on-device), local model
selection between MiniCPM5-2B and Qwen3-1.7B, explicit setup/download states,
and active execution hints.
Notes are always generated in the cloud; chat can run on the device.

Derived from Docs/Phases.md Phase 7, Docs/Design.md §8, Docs/UIUX.md §11, and Prototype v2.
"""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_MICRO,
    FONT_SIZE_MUTED,
    FONT_SIZE_TITLE,
    MIN_TOUCH_TARGET,
    PILL_RADIUS,
    SPACING_4,
    SPACING_6,
    SPACING_8,
    SPACING_10,
    SPACING_12,
    SPACING_16,
)
from app.ui.card import ClayCard

MODEL_MINICPM = "minicpm5-2b"
MODEL_QWEN = "qwen3-1.7b"

MODEL_LABELS = {
    MODEL_MINICPM: "MiniCPM5-2B · 1.56 GB",
    MODEL_QWEN: "Qwen3-1.7B · 1.1 GB",
}

EXPLANATORY_COPY = "Notes are always generated in the cloud. Chat can run on this device."
RUNNING_SLOWER_HINT = "running on device · slower"
SETTING_UP_HINT = "setting up local model…"


class ChatModelCard(ClayCard):
    """Settings card managing the Chat model selection (Cloud | Local)."""

    def __init__(
        self,
        *,
        chat_model: str = "cloud",
        local_model_id: str = MODEL_MINICPM,
        is_local_ready: bool = False,
        is_downloading: bool = False,
        download_progress: float | None = None,
        setup_status_text: str | None = None,
        on_model_change: Callable[[str], None] | None = None,
        on_local_model_pick: Callable[[str], None] | None = None,
        on_request_setup: Callable[[str], None] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
        width: float | None = None,
    ) -> None:
        self.theme_mode_val = theme_mode
        self._chat_model = chat_model.lower()
        self._local_model_id = local_model_id
        self._is_local_ready = is_local_ready
        self._is_downloading = is_downloading
        self._download_progress = download_progress
        self._setup_status_text = setup_status_text

        self.on_model_change = on_model_change
        self.on_local_model_pick = on_local_model_pick
        self.on_request_setup = on_request_setup

        palette = get_palette(theme_mode)

        # 1. Title Row: "Chat model" + Segmented Toggle (Cloud | Local)
        self.title_text = ft.Text(
            value="Chat model",
            size=FONT_SIZE_TITLE,
            weight=ft.FontWeight.W_700,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
        )

        self.cloud_btn = self._build_engine_button("Cloud", is_active=(self._chat_model == "cloud"))
        self.local_btn = self._build_engine_button("Local", is_active=(self._chat_model == "local"))

        toggle_row = ft.Row(
            controls=[self.cloud_btn, self.local_btn],
            spacing=SPACING_4,
            tight=True,
        )

        top_row = ft.Row(
            controls=[
                self.title_text,
                toggle_row,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # 2. Mandatory Explanatory Copy
        self.copy_text = ft.Text(
            value=EXPLANATORY_COPY,
            size=FONT_SIZE_MUTED,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
        )

        # 3. Active execution hint ("running on device · slower")
        self.hint_text = ft.Text(
            value=RUNNING_SLOWER_HINT,
            size=FONT_SIZE_MICRO,
            weight=ft.FontWeight.W_500,
            color=palette["accent_ink"],
            font_family=FONT_FAMILY_UI,
            visible=(self._chat_model == "local" and self._is_local_ready and not self._is_downloading),
        )

        # 4. Local Model Picker Row
        self.picker_label = ft.Text(
            value="Local chat model",
            size=FONT_SIZE_BODY,
            weight=ft.FontWeight.W_600,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
        )

        self.chip_minicpm = self._build_model_chip(
            MODEL_MINICPM,
            MODEL_LABELS[MODEL_MINICPM],
            is_active=(self._local_model_id == MODEL_MINICPM),
        )
        self.chip_qwen = self._build_model_chip(
            MODEL_QWEN,
            MODEL_LABELS[MODEL_QWEN],
            is_active=(self._local_model_id == MODEL_QWEN),
        )

        picker_chips_row = ft.Row(
            controls=[self.chip_minicpm, self.chip_qwen],
            spacing=SPACING_6,
            tight=True,
            wrap=True,
        )

        self.local_picker_section = ft.Column(
            controls=[
                ft.Divider(height=1.0, color=palette["line"]),
                ft.Row(
                    controls=[self.picker_label, picker_chips_row],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=SPACING_10,
            visible=(self._chat_model == "local"),
        )

        # 5. Local Setup / Download Progress State
        self.setup_label = ft.Text(
            value=self._setup_status_text or SETTING_UP_HINT,
            size=FONT_SIZE_MICRO,
            color=palette["accent_ink"],
            font_family=FONT_FAMILY_UI,
        )

        self.progress_bar = ft.ProgressBar(
            value=self._download_progress,
            color=palette["accent"],
            bgcolor=palette["accent_bg"],
            height=4.0,
            visible=self._is_downloading,
        )

        self.setup_button = ft.OutlinedButton(
            content=ft.Text("Download model", size=FONT_SIZE_MICRO),
            on_click=lambda _: self._handle_setup_click(),
            height=MIN_TOUCH_TARGET,
            visible=(self._chat_model == "local" and not self._is_local_ready and not self._is_downloading),
        )

        self.setup_section = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, size=16.0, color=palette["accent"]),
                        self.setup_label,
                    ],
                    spacing=SPACING_6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self.progress_bar,
                self.setup_button,
            ],
            spacing=SPACING_6,
            visible=(self._chat_model == "local" and not self._is_local_ready),
        )

        # Assembled Card Content
        card_content = ft.Column(
            controls=[
                top_row,
                self.copy_text,
                self.hint_text,
                self.local_picker_section,
                self.setup_section,
            ],
            spacing=SPACING_8,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        )

        super().__init__(
            content=card_content,
            padding=SPACING_12,
            theme_mode=theme_mode,
            width=width,
        )

    def _build_engine_button(self, label: str, *, is_active: bool) -> ft.Container:
        """Create a segmented engine toggle button."""
        palette = get_palette(self.theme_mode_val)
        bg = palette["accent_bg"] if is_active else "transparent"
        text_color = palette["accent_ink"] if is_active else palette["muted"]
        border = ft.Border.all(width=1.0, color=palette["accent"]) if is_active else ft.Border.all(width=1.0, color=palette["line"])

        btn_content = ft.Text(
            value=label,
            size=FONT_SIZE_MICRO,
            weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.NORMAL,
            color=text_color,
            font_family=FONT_FAMILY_UI,
        )

        def _on_click(e: Any) -> None:
            new_model = label.lower()
            if new_model != self._chat_model:
                self.set_chat_model(new_model)
                if self.on_model_change is not None:
                    self.on_model_change(new_model)

        return ft.Container(
            content=btn_content,
            bgcolor=bg,
            border=border,
            border_radius=ft.BorderRadius.all(PILL_RADIUS),
            padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_6),
            height=MIN_TOUCH_TARGET,
            alignment=ft.Alignment(0, 0),
            on_click=_on_click,
            tooltip=f"Switch to {label} chat model",
        )

    def _build_model_chip(self, model_id: str, label: str, *, is_active: bool) -> ft.Container:
        """Create an outlined or filled chip for local model selection."""
        palette = get_palette(self.theme_mode_val)
        bg = palette["accent_bg"] if is_active else palette["card"]
        text_color = palette["accent_ink"] if is_active else palette["ink"]
        border = ft.Border.all(width=1.0, color=palette["accent"]) if is_active else ft.Border.all(width=1.0, color=palette["line"])

        text_control = ft.Text(
            value=label,
            size=FONT_SIZE_MICRO,
            weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.NORMAL,
            color=text_color,
            font_family=FONT_FAMILY_UI,
            no_wrap=True,
        )

        def _on_click(e: Any) -> None:
            if self._local_model_id != model_id:
                self.set_local_model_id(model_id)
                if self.on_local_model_pick is not None:
                    self.on_local_model_pick(model_id)

        return ft.Container(
            content=text_control,
            bgcolor=bg,
            border=border,
            border_radius=ft.BorderRadius.all(PILL_RADIUS),
            padding=ft.Padding.symmetric(horizontal=SPACING_10, vertical=SPACING_6),
            height=MIN_TOUCH_TARGET,
            alignment=ft.Alignment(0, 0),
            on_click=_on_click,
            tooltip=f"Select {label}",
        )

    def _handle_setup_click(self) -> None:
        """Explicit user initiation of local model setup."""
        if self.on_request_setup is not None:
            self.on_request_setup(self._local_model_id)

    def set_chat_model(self, chat_model: str) -> None:
        """Update chat model selection and refresh visible sections."""
        self._chat_model = chat_model.lower()
        is_cloud = self._chat_model == "cloud"

        # Update button styles
        self.cloud_btn = self._build_engine_button("Cloud", is_active=is_cloud)
        self.local_btn = self._build_engine_button("Local", is_active=not is_cloud)

        # Update top row
        if isinstance(self.content, ft.Column) and len(self.content.controls) >= 1:
            top_row = self.content.controls[0]
            if isinstance(top_row, ft.Row) and len(top_row.controls) >= 2:
                top_row.controls[1] = ft.Row(
                    controls=[self.cloud_btn, self.local_btn],
                    spacing=SPACING_4,
                    tight=True,
                )

        # Visibility adjustments
        self.local_picker_section.visible = not is_cloud
        self.hint_text.visible = not is_cloud and self._is_local_ready and not self._is_downloading
        self.setup_section.visible = not is_cloud and not self._is_local_ready

    def set_local_model_id(self, model_id: str) -> None:
        """Update active local model ID and refresh chips."""
        self._local_model_id = model_id
        self.chip_minicpm = self._build_model_chip(
            MODEL_MINICPM,
            MODEL_LABELS[MODEL_MINICPM],
            is_active=(model_id == MODEL_MINICPM),
        )
        self.chip_qwen = self._build_model_chip(
            MODEL_QWEN,
            MODEL_LABELS[MODEL_QWEN],
            is_active=(model_id == MODEL_QWEN),
        )
        # Update row
        if len(self.local_picker_section.controls) >= 2:
            picker_row = self.local_picker_section.controls[1]
            if isinstance(picker_row, ft.Row) and len(picker_row.controls) >= 2:
                picker_row.controls[1] = ft.Row(
                    controls=[self.chip_minicpm, self.chip_qwen],
                    spacing=SPACING_6,
                    tight=True,
                    wrap=True,
                )

    def set_download_state(
        self,
        *,
        is_downloading: bool,
        progress: float | None = None,
        status_text: str | None = None,
        is_ready: bool = False,
    ) -> None:
        """Update local model setup progress from device runtime."""
        self._is_downloading = is_downloading
        self._download_progress = progress
        self._is_local_ready = is_ready
        self._setup_status_text = status_text

        self.progress_bar.visible = is_downloading
        self.progress_bar.value = progress

        label_val = status_text or (SETTING_UP_HINT if is_downloading else "Model not downloaded")
        self.setup_label.value = label_val

        self.setup_button.visible = not is_ready and not is_downloading
        self.setup_section.visible = (self._chat_model == "local" and not is_ready)
        self.hint_text.visible = (self._chat_model == "local" and is_ready and not is_downloading)
