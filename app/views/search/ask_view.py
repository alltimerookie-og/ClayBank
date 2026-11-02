"""Ask contextual assistant view component for ClayBank (Phase 6 deliverable P6-04).

Derived from Docs/Phases.md Phase 6, Docs/Design.md §7.6,
Docs/UIUX.md §10, and Prototype v2 Screen 13.
Renders:
- Breadcrumb / back navigation ("‹ Search" or "‹ {Folder Name}").
- Header title ("Ask your library" or "Ask {Folder Name}") with Scope chip ("Scope: Library" / "Scope: {Folder}").
- Suggested prompt pills ("Summarize this week", "What did I never open?", etc.).
- Conversational message stream (user bubble, assistant answer card with grounded citations).
- Typing dots progress indicator.
- Question text field + submit button.
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
    SPACING_16,
)
from app.views.search.ask_message import (
    AskAnswerCard,
    AskTypingDots,
    AskUserBubble,
)

DEFAULT_LIBRARY_PROMPTS = [
    "Summarize this week",
    "What did I never open?",
    "Find contradictory advice across saves",
]

DEFAULT_FOLDER_PROMPTS = [
    "Summarize this folder",
    "What are the key takeaways?",
    "Find actionable advice in these saves",
]


class AskView(ft.Column):
    """Contextual Ask AI view for library-wide or folder-scoped queries."""

    def __init__(
        self,
        *,
        scope: str | None = None,
        folder_name: str | None = None,
        on_back: Callable[[], None] | None = None,
        on_ask_query: Callable[[str, str | None], dict[str, Any]] | None = None,
        on_click_citation: Callable[[str, str | None], None] | None = None,
        save_lookup: dict[str, Any] | None = None,
        suggested_prompts: Sequence[str] | None = None,
        initial_messages: Sequence[tuple[str, dict[str, Any]]] | None = None,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.scope = scope or ("library" if not folder_name else folder_name)
        self.folder_name = folder_name
        self.on_back_callback = on_back
        self.on_ask_query = on_ask_query
        self.on_click_citation = on_click_citation
        self.save_lookup = dict(save_lookup or {})
        self.theme_mode_val = theme_mode
        self.conversation_history: list[tuple[str, dict[str, Any]]] = []
        self.is_processing = False
        self.typing_dots: AskTypingDots | None = None

        palette = get_palette(theme_mode)

        # Determine labels based on scope
        if self.scope == "library" and not folder_name:
            self.back_label = "Search"
            self.title_label = "Ask your library"
            self.scope_chip_text = "Library"
            default_prompts = DEFAULT_LIBRARY_PROMPTS
        else:
            display_folder = folder_name or self.scope
            self.back_label = display_folder
            self.title_label = f"Ask {display_folder}"
            self.scope_chip_text = display_folder
            default_prompts = [
                f"Summarize {display_folder}",
                "What are the key takeaways?",
                "Find actionable advice in these saves",
            ]

        self.prompts = list(suggested_prompts) if suggested_prompts is not None else default_prompts

        # 1. Header: Back button + Title + Scope Chip
        self.back_button = ft.TextButton(
            f"‹ {self.back_label}",
            on_click=lambda _: self._handle_back(),
            style=ft.ButtonStyle(color=palette["accent_ink"]),
        )

        self.title_text = ft.Text(
            self.title_label,
            size=FONT_SIZE_TITLE,
            weight=ft.FontWeight.BOLD,
            color=palette["ink"],
            font_family=FONT_FAMILY_UI,
        )

        self.scope_chip = ft.Container(
            content=ft.Text(
                f"Scope: {self.scope_chip_text}",
                size=FONT_SIZE_MICRO,
                color=palette["chip_ink"],
                weight=ft.FontWeight.W_600,
                font_family=FONT_FAMILY_UI,
            ),
            bgcolor=palette["chip"],
            border_radius=ft.BorderRadius.all(PILL_RADIUS),
            padding=ft.Padding.symmetric(horizontal=SPACING_8, vertical=SPACING_4),
        )

        header_row = ft.Row(
            controls=[
                self.back_button,
                self.title_text,
                ft.Container(expand=True),
                self.scope_chip,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # 2. Suggested Prompts Row
        prompt_chips: list[ft.Control] = []
        for p in self.prompts:
            def _make_prompt_handler(prompt_text=p):
                return lambda _: self.submit_question(prompt_text)

            chip_btn = ft.Container(
                content=ft.Text(
                    p,
                    size=FONT_SIZE_MUTED,
                    color=palette["ink"],
                    font_family=FONT_FAMILY_UI,
                ),
                bgcolor=palette["card"],
                border=ft.Border.all(1.0, palette["line"]),
                border_radius=ft.BorderRadius.all(PILL_RADIUS),
                padding=ft.Padding.symmetric(horizontal=SPACING_12, vertical=SPACING_6),
                on_click=_make_prompt_handler(p),
            )
            prompt_chips.append(chip_btn)

        self.suggestions_section = ft.Column(
            controls=[
                ft.Text(
                    "Suggested prompts",
                    size=FONT_SIZE_MICRO,
                    color=palette["muted"],
                    weight=ft.FontWeight.W_600,
                    font_family=FONT_FAMILY_UI,
                ),
                ft.Row(
                    controls=prompt_chips,
                    spacing=SPACING_8,
                    wrap=True,
                ),
            ],
            spacing=SPACING_6,
        )

        # 3. Message Stream List
        self.message_list = ft.ListView(
            expand=True,
            spacing=SPACING_12,
            padding=ft.Padding.symmetric(horizontal=SPACING_16, vertical=SPACING_8),
        )
        self.message_list.controls.append(self.suggestions_section)

        # If initial messages provided, populate them
        if initial_messages:
            for q, a in initial_messages:
                self._append_message_pair(q, a)

        # 4. Bottom Input Bar
        self.input_field = ft.TextField(
            hint_text="Ask anything about your saves...",
            hint_style=ft.TextStyle(color=palette["muted"], size=FONT_SIZE_BODY),
            text_size=FONT_SIZE_BODY,
            color=palette["ink"],
            bgcolor=palette["card"],
            border_radius=ft.BorderRadius.all(22.0),
            border_color=palette["line"],
            content_padding=ft.Padding.symmetric(horizontal=SPACING_16, vertical=SPACING_8),
            expand=True,
            on_submit=lambda _: self._handle_input_submit(),
        )

        self.send_button = ft.IconButton(
            icon=ft.Icons.ARROW_UPWARD,
            icon_color=palette["accent_fg"],
            bgcolor=palette["accent"],
            icon_size=18,
            on_click=lambda _: self._handle_input_submit(),
        )

        input_row = ft.Row(
            controls=[self.input_field, self.send_button],
            spacing=SPACING_8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        input_container = ft.Container(
            content=input_row,
            bgcolor=palette["card"],
            border=ft.Border(top=ft.BorderSide(1.0, palette["line"])),
            padding=ft.Padding.symmetric(horizontal=SPACING_16, vertical=SPACING_8),
        )

        super().__init__(
            controls=[
                ft.Container(content=header_row, padding=ft.Padding.symmetric(horizontal=SPACING_16, vertical=SPACING_8)),
                self.message_list,
                input_container,
            ],
            expand=True,
            spacing=0,
        )

    def _safe_update(self, control: ft.Control | None = None) -> None:
        """Safely trigger update without failing if control is unmounted."""
        target = control or self
        try:
            target.update()
        except Exception:
            pass

    def _handle_back(self) -> None:
        """Invoke on_back callback if provided."""
        if self.on_back_callback:
            self.on_back_callback()

    def _handle_input_submit(self) -> None:
        """Handle submit from text field or send button."""
        val = self.input_field.value
        self.input_field.value = ""
        self._safe_update(self.input_field)
        if val:
            self.submit_question(val)

    def submit_question(self, question: str) -> None:
        """Submit a question to the assistant and render streaming progress."""
        text = question.strip()
        if not text or self.is_processing:
            return

        self.is_processing = True
        self.send_button.disabled = True

        # 1. Add user question bubble
        bubble = AskUserBubble(text, theme_mode=self.theme_mode_val)
        self.message_list.controls.append(bubble)

        # 2. Add typing dots indicator
        self.typing_dots = AskTypingDots(theme_mode=self.theme_mode_val)
        self.message_list.controls.append(self.typing_dots)

        self._safe_update(self.message_list)
        self._safe_update(self.send_button)

        # 3. Request answer
        answer_data: dict[str, Any]
        if self.on_ask_query:
            try:
                answer_data = self.on_ask_query(text, self.scope)
            except Exception as e:
                answer_data = {
                    "answer": f"Unable to process question: {e}",
                    "scope": self.scope,
                    "engine": "cloud",
                    "citations": [],
                }
        else:
            # Standalone fallback answer conforming to ask-answer.json
            answer_data = {
                "answer": f"Here is what was found regarding “{text}”.",
                "scope": self.scope,
                "engine": "cloud",
                "citations": [
                    {
                        "save_id": "018f4c1a-0000-7de6-9c8e-000000000001",
                        "anchor": "overview",
                        "quote": text,
                    }
                ],
            }

        # 4. Remove typing dots and add answer card
        if self.typing_dots in self.message_list.controls:
            self.message_list.controls.remove(self.typing_dots)
            self.typing_dots = None

        card = AskAnswerCard(
            answer_data,
            on_click_citation=self.on_click_citation,
            save_lookup=self.save_lookup,
            theme_mode=self.theme_mode_val,
        )
        self.message_list.controls.append(card)
        self.conversation_history.append((text, answer_data))

        self.is_processing = False
        self.send_button.disabled = False

        self._safe_update(self.message_list)
        self._safe_update(self.send_button)

    def _append_message_pair(self, question: str, answer_data: dict[str, Any]) -> None:
        """Append an existing question and answer pair to the stream."""
        bubble = AskUserBubble(question, theme_mode=self.theme_mode_val)
        card = AskAnswerCard(
            answer_data,
            on_click_citation=self.on_click_citation,
            save_lookup=self.save_lookup,
            theme_mode=self.theme_mode_val,
        )
        self.message_list.controls.append(bubble)
        self.message_list.controls.append(card)
        self.conversation_history.append((question, answer_data))
