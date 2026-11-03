"""OpenAI-compatible chat provider protocol."""

from __future__ import annotations

from typing import Protocol

from Backend.config import Settings


class ChatMessage(Protocol):
    """Structural chat message shape."""

    @property
    def role(self) -> str:
        """Message role."""
        ...

    @property
    def content(self) -> str:
        """Message content."""
        ...


class ChatProvider(Protocol):
    """Structural cloud answer-generation source."""

    def answer(self, question: str, context: str) -> str | None:
        """Generate a cited Markdown answer from retrieved context."""
        ...


def provider_from_settings(settings: Settings) -> ChatProvider | None:
    """Select the configured cloud chat provider."""
    from Backend.llm.meta_model import MetaModelProvider

    provider = MetaModelProvider(settings)
    return provider if provider.enabled else None
