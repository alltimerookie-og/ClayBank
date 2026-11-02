"""Meta Model API client conforming to OpenAI-compatible Chat Completions (Rules.md, ADR 0005)."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import httpx

from backend.config import settings
from backend.llm.models import NoteGenerationResult, NoteStructuredOutput
from backend.llm.prompts import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)

# Request & retry constraints
DEFAULT_CONNECT_TIMEOUT = 5.0
DEFAULT_READ_TIMEOUT = 30.0
MAX_TRANSIENT_RETRIES = 2
INITIAL_RETRY_DELAY = 0.5


class MetaLLMProvider:
    """OpenAI-compatible LLM provider targeting the Meta Model API."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = (base_url or settings.META_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.META_API_KEY
        self.model = model or settings.META_MODEL_NOTES
        self._client = client

    async def generate_note(
        self,
        title: str,
        kind: str,
        content: str,
        user_context: str | None = None,
    ) -> NoteGenerationResult:
        """Generate structured note sections via Chat Completions endpoint."""
        # 1. Credential enforcement: live credentials required
        key = (self.api_key or "").strip()
        if not key:
            logger.warning("Meta Model API key is missing or empty; note generation unavailable")
            return NoteGenerationResult(
                is_success=False,
                error_category="missing_credentials",
                provider="meta",
                model=self.model,
            )

        # 2. Check for usable source text
        if not content or not content.strip():
            return NoteGenerationResult(
                is_success=False,
                error_category="empty_content",
                provider="meta",
                model=self.model,
            )

        # 3. Assemble prompt with boundary defenses and truncation budget
        user_prompt = build_user_prompt(title, kind, content, user_context)

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "ClayBank/1.0 (+https://github.com/alltimerookie-og/ClayBank)",
        }

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

        url = f"{self.base_url}/chat/completions"
        timeout = httpx.Timeout(
            connect=DEFAULT_CONNECT_TIMEOUT,
            read=DEFAULT_READ_TIMEOUT,
            write=5.0,
            pool=5.0,
        )

        if self._client is not None:
            return await self._execute_request(self._client, url, headers, payload)

        async with httpx.AsyncClient(timeout=timeout) as client:
            return await self._execute_request(client, url, headers, payload)

    async def _execute_request(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> NoteGenerationResult:
        """Execute HTTP request with bounded transient retries and safe error mapping."""
        last_category = "unknown_error"

        for attempt in range(MAX_TRANSIENT_RETRIES + 1):
            try:
                resp = await client.post(url, headers=headers, json=payload)

                # HTTP Status handling
                if resp.status_code == 200:
                    return self._parse_successful_response(resp.json())

                if resp.status_code == 401:
                    logger.warning("Meta API authentication failed: 401 Unauthorized")
                    return NoteGenerationResult(
                        is_success=False,
                        error_category="auth_failed",
                        provider="meta",
                        model=self.model,
                    )

                if resp.status_code == 403:
                    logger.warning("Meta API authorization forbidden: 403 Forbidden")
                    return NoteGenerationResult(
                        is_success=False,
                        error_category="forbidden",
                        provider="meta",
                        model=self.model,
                    )

                if resp.status_code == 429:
                    logger.warning("Meta API rate limited: 429 Too Many Requests")
                    return NoteGenerationResult(
                        is_success=False,
                        error_category="rate_limited",
                        provider="meta",
                        model=self.model,
                    )

                if resp.status_code == 422:
                    logger.warning("Meta API rejected request format: 422 Unprocessable Entity")
                    return NoteGenerationResult(
                        is_success=False,
                        error_category="validation_error",
                        provider="meta",
                        model=self.model,
                    )

                if 500 <= resp.status_code < 600:
                    last_category = "server_error"
                    logger.warning("Meta API server error %d (attempt %d)", resp.status_code, attempt + 1)
                    if attempt < MAX_TRANSIENT_RETRIES:
                        await asyncio.sleep(INITIAL_RETRY_DELAY * (2 ** attempt))
                        continue
                    return NoteGenerationResult(
                        is_success=False,
                        error_category="server_error",
                        provider="meta",
                        model=self.model,
                    )

                last_category = f"http_{resp.status_code}"
                return NoteGenerationResult(
                    is_success=False,
                    error_category=last_category,
                    provider="meta",
                    model=self.model,
                )

            except (httpx.ConnectError, httpx.ConnectTimeout) as err:
                last_category = "connection_failed"
                logger.warning("Meta API connection error on attempt %d: %s", attempt + 1, type(err).__name__)
                if attempt < MAX_TRANSIENT_RETRIES:
                    await asyncio.sleep(INITIAL_RETRY_DELAY * (2 ** attempt))
                    continue
                return NoteGenerationResult(
                    is_success=False,
                    error_category="connection_failed",
                    provider="meta",
                    model=self.model,
                )

            except httpx.ReadTimeout:
                logger.warning("Meta API read timeout exceeded (%ds)", DEFAULT_READ_TIMEOUT)
                return NoteGenerationResult(
                    is_success=False,
                    error_category="timeout",
                    provider="meta",
                    model=self.model,
                )

            except Exception as err:
                logger.warning("Meta API unexpected error: %s", type(err).__name__)
                return NoteGenerationResult(
                    is_success=False,
                    error_category="unknown_error",
                    provider="meta",
                    model=self.model,
                )

        return NoteGenerationResult(
            is_success=False,
            error_category=last_category,
            provider="meta",
            model=self.model,
        )

    def _parse_successful_response(self, data: dict[str, Any]) -> NoteGenerationResult:
        """Parse, clean, and validate OpenAI-compatible JSON Chat Completion."""
        try:
            choices = data.get("choices") or []
            if not choices:
                return NoteGenerationResult(
                    is_success=False,
                    error_category="empty_choices",
                    provider="meta",
                    model=self.model,
                )

            choice = choices[0]
            message = choice.get("message") or {}
            raw_content = message.get("content") or ""
            if not isinstance(raw_content, str) or not raw_content.strip():
                return NoteGenerationResult(
                    is_success=False,
                    error_category="empty_completion",
                    provider="meta",
                    model=self.model,
                )

            # Strip markdown code fences if model wrapped JSON
            cleaned = raw_content.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(r"\s*```$", "", cleaned)
                cleaned = cleaned.strip()

            parsed_json = json.loads(cleaned)
            if not isinstance(parsed_json, dict):
                return NoteGenerationResult(
                    is_success=False,
                    error_category="invalid_json_type",
                    provider="meta",
                    model=self.model,
                )

            # Enforce schema validity with Pydantic model
            structured = NoteStructuredOutput.model_validate(parsed_json)

            tokens = 0
            usage = data.get("usage")
            if isinstance(usage, dict):
                tokens = int(usage.get("total_tokens") or 0)

            logger.info("Meta LLM note generation completed: model=%s tokens=%d", self.model, tokens)
            return NoteGenerationResult(
                is_success=True,
                structured_output=structured,
                raw_text=raw_content,
                provider="meta",
                model=self.model,
                tokens_used=tokens,
            )

        except Exception as exc:
            logger.warning("Failed to validate structured output from Meta LLM: %s", exc)
            return NoteGenerationResult(
                is_success=False,
                error_category="schema_validation_failed",
                provider="meta",
                model=self.model,
            )
