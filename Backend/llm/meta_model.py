"""Meta Model API provider."""

from __future__ import annotations

from Backend.config import Settings
from Backend.errors import DomainError


class MetaModelProvider:
    """OpenAI-compatible cloud answer generation."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        """Whether cloud answer generation is configured."""
        return bool(
            self.settings.meta_model_base_url
            and self.settings.meta_model_api_key
            and self.settings.meta_model_name
            and not self.settings.meta_model_contributor_tier
        )

    def answer(self, question: str, context: str) -> str | None:
        """Generate a cited Markdown answer from retrieved context."""
        if self.settings.meta_model_contributor_tier:
            raise DomainError(
                "validation",
                "Contributor training tier is forbidden",
            )
        if not self.enabled:
            return None
        import httpx

        response = httpx.post(
            f"{self.settings.meta_model_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self.settings.meta_model_api_key}"},
            json={
                "model": self.settings.meta_model_name,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Answer using only the provided saves. "
                            "Return Markdown and cite save IDs inline like [save:ID]."
                        ),
                    },
                    {"role": "user", "content": f"Question: {question}\n\nContext:\n{context}"},
                ],
            },
            timeout=120,
        )
        try:
            response.raise_for_status()
        except Exception as exc:
            raise DomainError("llm_unavailable", "Cloud answer generation failed") from exc
        payload = response.json()
        try:
            text = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise DomainError("llm_unavailable", "Cloud answer generation failed")
        if not isinstance(text, str) or not text.strip():
            raise DomainError("llm_unavailable", "Cloud answer generation failed")
        return text.strip()
