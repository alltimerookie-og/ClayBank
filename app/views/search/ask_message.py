"""Conversational message bubble and answer card components for Ask (Phase 6 deliverable P6-03).

Derived from Docs/Phases.md Phase 6, Docs/Design.md §7.6,
Docs/UIUX.md §10, and Prototype v2 Screen 13.
Renders:
- User question bubble (right-aligned, terracotta accent).
- Typing dots progress indicator.
- Assistant answer card with Markdown body, mandatory citation chips,
  and local-engine slower hint.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence
import flet as ft

from app.shell.theme import get_palette
from app.shell.tokens import (
    FONT_FAMILY_UI,
    FONT_SIZE_BODY,
    FONT_SIZE_MICRO,
    FONT_SIZE_MUTED,
    FONT_SIZE_TITLE,
    PILL_RADIUS,
    SPACING_4,
    SPACING_6,
    SPACING_8,
    SPACING_12,
    create_text_style,
)
from app.ui.card import ClayCard
from app.ui.chips import CitationChip


class AskUserBubble(ft.Row):
    """Right-aligned user chat message bubble in terracotta accent."""

    def __init__(
        self,
        message: str,
        *,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.message = message
        palette = get_palette(theme_mode)

        text_control = ft.Text(
            value=message,
            size=FONT_SIZE_BODY,
            color=palette["accent_fg"],
            font_family=FONT_FAMILY_UI,
        )

        bubble_container = ft.Container(
            content=text_control,
            bgcolor=palette["accent"],
            padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
            border_radius=ft.BorderRadius.only(
                top_left=18.0,
                top_right=18.0,
                bottom_left=18.0,
                bottom_right=4.0,
            ),
        )

        super().__init__(
            controls=[
                ft.Container(expand=True),
                bubble_container,
            ],
            alignment=ft.MainAxisAlignment.END,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )


class AskTypingDots(ft.Row):
    """Loading indicator card displayed while assistant processes an answer."""

    def __init__(
        self,
        *,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        palette = get_palette(theme_mode)

        dots_row = ft.Row(
            controls=[
                ft.Container(width=6.0, height=6.0, border_radius=3.0, bgcolor=palette["accent"]),
                ft.Container(width=6.0, height=6.0, border_radius=3.0, bgcolor=palette["muted"]),
                ft.Container(width=6.0, height=6.0, border_radius=3.0, bgcolor=palette["accent"]),
            ],
            spacing=SPACING_4,
            alignment=ft.MainAxisAlignment.CENTER,
        )

        card_container = ft.Container(
            content=dots_row,
            bgcolor=palette["card"],
            border=ft.Border.all(1.0, palette["line"]),
            border_radius=ft.BorderRadius.all(18.0),
            padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_8),
            width=70.0,
        )

        super().__init__(
            controls=[card_container, ft.Container(expand=True)],
            alignment=ft.MainAxisAlignment.START,
        )


class AskAnswerCard(ClayCard):
    """Assistant response card with Markdown answer and mandatory citation chips."""

    def __init__(
        self,
        answer_data: dict[str, Any],
        *,
        on_click_citation: Callable[[str, str | None], None] | None = None,
        save_lookup: dict[str, Any] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.answer_data = dict(answer_data)
        self.raw_answer = str(answer_data.get("answer") or "")
        self.scope = answer_data.get("scope")
        self.engine = answer_data.get("engine", "cloud")
        raw_citations = answer_data.get("citations")
        self.citations: list[dict[str, Any]] = list(raw_citations) if raw_citations else []
        self.on_click_citation = on_click_citation
        self.save_lookup = dict(save_lookup or {})
        self.theme_mode_val = theme_mode

        palette = get_palette(theme_mode)

        card_controls: list[ft.Control] = []

        # 1. Answer text / Markdown
        if self.raw_answer:
            answer_text = ft.Markdown(
                value=self.raw_answer,
                extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                selectable=True,
            )
            card_controls.append(answer_text)

        # 2. Invariant Check: Citations are MANDATORY (Answer without citations = bug)
        if not self.citations:
            invalid_text = ft.Text(
                "Warning: Answer has no grounded citations.",
                size=FONT_SIZE_MUTED,
                color=palette["accent"],
                font_family=FONT_FAMILY_UI,
                italic=True,
            )
            card_controls.append(invalid_text)
        else:
            # Subtitle
            cnt = len(self.citations)
            sub_label = f"Based on {cnt} save" if cnt == 1 else f"Based on {cnt} saves"
            subtitle = ft.Text(
                f"{sub_label} · every answer cites what it used",
                size=FONT_SIZE_MUTED,
                color=palette["muted"],
                font_family=FONT_FAMILY_UI,
            )
            card_controls.append(subtitle)

            # Citation Chips Row
            chips: list[ft.Control] = []
            for cit in self.citations:
                s_id = str(cit.get("save_id") or "")
                anchor = cit.get("anchor")
                quote = cit.get("quote")

                # Resolve label from save metadata or anchor or quote
                save_meta = self.save_lookup.get(s_id)
                if save_meta and isinstance(save_meta, dict):
                    label_text = str(save_meta.get("title") or save_meta.get("user_context") or "Save")
                elif quote:
                    label_text = f"“{quote}”"
                else:
                    label_text = "Cited note"

                chip_label = f"→ {label_text}"
                if anchor:
                    chip_label = f"{chip_label} ({anchor})"

                def _make_jump(save_id_val=s_id, anchor_val=anchor):
                    if self.on_click_citation:
                        self.on_click_citation(save_id_val, anchor_val)

                chip = CitationChip(
                    label=chip_label,
                    save_id=s_id,
                    target_offset=anchor,
                    on_click=lambda _, s=s_id, a=anchor: self._handle_citation_click(s, a),
                    theme_mode=theme_mode,
                )
                chips.append(chip)

            chips_row = ft.Row(
                controls=chips,
                spacing=SPACING_6,
                wrap=True,
            )
            card_controls.append(chips_row)

        # 3. Local engine slower hint
        if self.engine == "local":
            hint_text = ft.Text(
                "running on device · slower",
                size=FONT_SIZE_MICRO,
                color=palette["muted"],
                font_family=FONT_FAMILY_UI,
                italic=True,
            )
            card_controls.append(hint_text)

        col = ft.Column(
            controls=card_controls,
            spacing=SPACING_8,
            tight=True,
        )

        super().__init__(
            content=col,
            padding=SPACING_12,
            theme_mode=theme_mode,
        )
        self.border_radius = ft.BorderRadius.only(
            top_left=18.0,
            top_right=18.0,
            bottom_left=4.0,
            bottom_right=18.0,
        )

    def _handle_citation_click(self, save_id: str, anchor: str | None) -> None:
        """Propagate citation navigation to coordinator."""
        if self.on_click_citation:
            self.on_click_citation(save_id, anchor)
