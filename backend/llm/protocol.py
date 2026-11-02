"""Protocol abstraction for cloud LLM note generation providers (Rules.md §8, ADR 0005)."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.llm.models import NoteGenerationResult


@runtime_checkable
class LLMProvider(Protocol):
    """Asynchronous contract for note generation providers."""

    async def generate_note(
        self,
        title: str,
        kind: str,
        content: str,
        user_context: str | None = None,
    ) -> NoteGenerationResult:
        """Generate structured note sections from extracted source content.

        Args:
            title: Title of the save.
            kind: Save kind ('video', 'article', 'unknown').
            content: Raw transcript or extracted article body.
            user_context: Optional capture-time note provided by the user.

        Returns:
            NoteGenerationResult: Structured output and execution metadata.
        """
        ...
