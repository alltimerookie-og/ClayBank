"""Cloud LLM note generation interfaces and Meta Model API client (Rules.md, ADR 0005)."""
from __future__ import annotations

from backend.llm.meta import MetaLLMProvider
from backend.llm.models import LinkItem, NoteGenerationResult, NoteStructuredOutput
from backend.llm.protocol import LLMProvider

__all__ = [
    "LLMProvider",
    "LinkItem",
    "NoteGenerationResult",
    "NoteStructuredOutput",
    "MetaLLMProvider",
]
