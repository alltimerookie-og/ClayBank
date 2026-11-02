"""Processing Stage Card for ClayBank.

Displays live progress for the 6 enrichment stages:
queued -> extracting -> transcribing -> analyzing -> sorting -> ready.
Gracefully handles degraded states, missing transcripts, and unknown formats.

Derived from Docs/Phases.md Phase 2, Docs/api/schemas/job.json, and Prototype v2.
"""

from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlparse
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    CARD_RADIUS,
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_LABEL,
    FONT_SIZE_MICRO,
    FONT_SIZE_MUTED,
    FONT_SIZE_TITLE,
    PILL_RADIUS,
    SPACING_4,
    SPACING_8,
    SPACING_12,
    SPACING_16,
)
from app.ui.card import ClayCard

STAGE_ORDER: tuple[str, ...] = (
    "queued",
    "extracting",
    "transcribing",
    "analyzing",
    "sorting",
    "ready",
)

STAGE_METADATA: dict[str, dict[str, Any]] = {
    "queued": {
        "title": "Queued",
        "description": "Waiting for enrichment worker...",
        "icon": ft.Icons.SCHEDULE_ROUNDED,
    },
    "extracting": {
        "title": "Extracting Content",
        "description": "Fetching page content, metadata & readable text...",
        "icon": ft.Icons.DOWNLOAD_ROUNDED,
    },
    "transcribing": {
        "title": "Transcribing Audio",
        "description": "Running local Whisper speech-to-text...",
        "icon": ft.Icons.GRAPHIC_EQ_ROUNDED,
    },
    "analyzing": {
        "title": "Synthesizing Summary",
        "description": "Synthesizing takeaways and semantic themes...",
        "icon": ft.Icons.AUTO_AWESOME_ROUNDED,
    },
    "sorting": {
        "title": "Predicting Folders",
        "description": "Comparing content embeddings to folder centroids...",
        "icon": ft.Icons.FOLDER_SPECIAL_ROUNDED,
    },
    "ready": {
        "title": "Ready",
        "description": "Processing complete and searchable in knowledge wallet.",
        "icon": ft.Icons.CHECK_CIRCLE_ROUNDED,
    },
}

POLL_INTERVALS_SEC: tuple[int, ...] = (1, 2, 3)


def get_poll_interval(attempt: int) -> int:
    """Return documented backoff polling interval: 1s, 2s, 3s."""
    if attempt < 0:
        return POLL_INTERVALS_SEC[0]
    if attempt < len(POLL_INTERVALS_SEC):
        return POLL_INTERVALS_SEC[attempt]
    return POLL_INTERVALS_SEC[-1]


class ProcessingCard(ClayCard):
    """Card displaying live status of asynchronous save enrichment pipeline."""

    def __init__(
        self,
        job_data: dict[str, Any],
        *,
        url: str = "",
        kind: str = "web",
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
        on_click: Callable[[Any], None] | None = None,
    ) -> None:
        self.save_url = url
        self.content_kind = kind
        self.job_data = dict(job_data)
        self.current_state = str(job_data.get("state", "queued"))
        self.theme_mode_val = theme_mode

        palette = get_palette(theme_mode)

        # Source URL or Domain title
        domain = self._extract_display_domain(url)
        self.domain_text = ft.Text(
            value=domain,
            size=FONT_SIZE_TITLE,
            weight=ft.FontWeight.W_700,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
            no_wrap=True,
        )

        # State badge pill
        self.state_badge_text = ft.Text(
            value=self.current_state.upper(),
            size=10.0,
            weight=ft.FontWeight.W_700,
            color=palette["accent_ink"],
            font_family=FONT_FAMILY_UI,
        )

        self.state_badge = ft.Container(
            content=self.state_badge_text,
            bgcolor=palette["accent_bg"],
            padding=ft.Padding.symmetric(horizontal=SPACING_8, vertical=2.0),
            border_radius=ft.BorderRadius.all(PILL_RADIUS),
        )

        header_row = ft.Row(
            controls=[
                self.domain_text,
                ft.Container(expand=True),
                self.state_badge,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Stage Icon, Title, and Description
        stage_info = STAGE_METADATA.get(self.current_state, STAGE_METADATA["queued"])
        self.stage_icon = ft.Icon(
            icon=stage_info["icon"],
            size=22.0,
            color=palette["accent"],
        )

        self.stage_title = ft.Text(
            value=stage_info["title"],
            size=FONT_SIZE_BODY,
            weight=ft.FontWeight.W_600,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
        )

        self.stage_desc = ft.Text(
            value=stage_info["description"],
            size=FONT_SIZE_MUTED,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
        )

        stage_text_column = ft.Column(
            controls=[self.stage_title, self.stage_desc],
            spacing=SPACING_4,
            expand=True,
        )

        stage_row = ft.Row(
            controls=[self.stage_icon, stage_text_column],
            spacing=SPACING_12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Determinate progress bar across the 6 stages
        progress_val = self._calculate_progress(self.current_state)
        self.progress_bar = ft.ProgressBar(
            value=progress_val,
            color=palette["accent"],
            bgcolor=palette["chip"],
        )

        # Degraded fallback banner (shown for missing transcript, unknown kind, etc.)
        self.degraded_banner_text = ft.Text(
            value="",
            size=FONT_SIZE_LABEL,
            color=palette["muted"],
            font_family=FONT_FAMILY_UI,
        )

        self.degraded_banner = ft.Row(
            controls=[
                ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=14.0, color=palette["muted"]),
                self.degraded_banner_text,
            ],
            spacing=SPACING_4,
            visible=False,
        )

        card_content = ft.Column(
            controls=[
                header_row,
                ft.Container(height=SPACING_8),
                stage_row,
                ft.Container(height=SPACING_8),
                self.progress_bar,
                self.degraded_banner,
            ],
            spacing=SPACING_4,
        )

        super().__init__(
            content=card_content,
            padding=SPACING_16,
            theme_mode=theme_mode,
            on_click=on_click,
        )

        # Check for degraded flags initially
        self._check_degraded_status()

    def update_job(self, job_data: dict[str, Any]) -> None:
        """Update live stage status and degraded state from polled backend job."""
        self.job_data = dict(job_data)
        self.current_state = str(job_data.get("state", self.current_state))
        palette = get_palette(self.theme_mode_val)

        stage_info = STAGE_METADATA.get(self.current_state, STAGE_METADATA["queued"])
        self.stage_icon.icon = stage_info["icon"]
        self.stage_title.value = stage_info["title"]
        self.stage_desc.value = stage_info["description"]
        self.state_badge_text.value = self.current_state.upper()

        if self.current_state == "ready":
            self.state_badge.bgcolor = palette["ok"]
            self.state_badge_text.color = palette["ok_ink"]
            self.stage_icon.color = palette["ok_ink"]
        else:
            self.state_badge.bgcolor = palette["accent_bg"]
            self.state_badge_text.color = palette["accent_ink"]
            self.stage_icon.color = palette["accent"]

        self.progress_bar.value = self._calculate_progress(self.current_state)
        self._check_degraded_status()

    def is_complete(self) -> bool:
        """Return whether processing has finished (ready)."""
        return self.current_state == "ready"

    def _calculate_progress(self, state: str) -> float:
        """Map state name to 0.0-1.0 progress fraction."""
        if state in STAGE_ORDER:
            idx = STAGE_ORDER.index(state)
            return round((idx + 1) / len(STAGE_ORDER), 2)
        return 0.16

    def _extract_display_domain(self, url: str) -> str:
        """Extract domain from URL or fallback to raw string."""
        if not url:
            return "New Save"
        try:
            parsed = urlparse(url)
            if parsed.netloc:
                return parsed.netloc.replace("www.", "")
        except Exception:
            pass
        return url[:30]

    def _check_degraded_status(self) -> None:
        """Display non-blocking fallback messages for missing audio or unknown formats."""
        skipped = self.job_data.get("skipped", [])
        failed = self.job_data.get("failed", [])
        error = self.job_data.get("error")

        if "transcribing" in skipped or "transcribing" in failed:
            self.degraded_banner_text.value = "Audio transcript unavailable — continuing with article summary"
            self.degraded_banner.visible = True
        elif self.content_kind == "unknown":
            self.degraded_banner_text.value = "Unknown content format — saved raw link"
            self.degraded_banner.visible = True
        elif error:
            self.degraded_banner_text.value = f"Encountered notice: {error}"
            self.degraded_banner.visible = True
        else:
            self.degraded_banner.visible = False
