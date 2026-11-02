"""Tests for Phase 4 Meta LLM provider, structured output parsing, error handling, and retries."""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from backend.llm.models import LinkItem, NoteGenerationResult, NoteStructuredOutput
from backend.llm.meta import MetaLLMProvider
from backend.llm.protocol import LLMProvider


def test_meta_provider_conforms_to_llm_protocol() -> None:
    """Verify MetaLLMProvider conforms to LLMProvider runtime Protocol."""
    provider = MetaLLMProvider(api_key="test-key")
    assert isinstance(provider, LLMProvider)


@pytest.mark.anyio
async def test_missing_api_key_returns_controlled_failure_without_network() -> None:
    """Verify missing/empty META_API_KEY immediately returns controlled failure with zero calls."""
    provider = MetaLLMProvider(api_key="")
    result = await provider.generate_note(
        title="Test",
        kind="article",
        content="Article text here",
    )
    assert not result.is_success
    assert result.error_category == "missing_credentials"
    assert result.structured_output is None


@pytest.mark.anyio
async def test_empty_content_returns_controlled_failure() -> None:
    """Verify empty/whitespace source content immediately returns controlled failure."""
    provider = MetaLLMProvider(api_key="test-key")
    result = await provider.generate_note(
        title="Test",
        kind="article",
        content="   \n\t  ",
    )
    assert not result.is_success
    assert result.error_category == "empty_content"


@pytest.mark.anyio
async def test_successful_structured_note_generation() -> None:
    """Verify successful 200 JSON Chat Completion produces populated NoteStructuredOutput."""
    sample_json = {
        "overview": "This talk explains modern microservices architecture and resilient distributed consensus.",
        "key_points": [
            "Use event-driven communication instead of synchronous RPC.",
            "Enforce bounded contexts across domains.",
            "Log audit changes idempotently.",
        ],
        "links": [
            {
                "url": "https://martinfowler.com/articles/patterns-legacy-displacement/",
                "anchor_text": "Strangler Fig Pattern",
                "jump_target": "04:15",
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer mock-secret-key"
        body = json.loads(request.read())
        assert body["model"] == "gpt-oss-120b"
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(sample_json)}}],
                "usage": {"total_tokens": 420},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = MetaLLMProvider(api_key="mock-secret-key", client=client)

    result = await provider.generate_note(
        title="Microservices Talk",
        kind="video",
        content="Spoken transcript about distributed systems.",
    )

    assert result.is_success
    assert result.error_category is None
    assert result.tokens_used == 420
    assert result.structured_output is not None
    assert "microservices architecture" in result.structured_output.overview
    assert len(result.structured_output.key_points) == 3
    assert len(result.structured_output.links) == 1
    assert result.structured_output.links[0].anchor_text == "Strangler Fig Pattern"
    assert result.structured_output.links[0].jump_target == "04:15"


@pytest.mark.anyio
async def test_markdown_code_fences_stripped_from_completion() -> None:
    """Verify completions wrapped in ```json ... ``` are cleaned and parsed safely."""
    inner_json = {
        "overview": "Overview from markdown fenced response.",
        "key_points": ["First point.", "Second point."],
        "links": [],
    }
    fenced_content = f"```json\n{json.dumps(inner_json)}\n```"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": fenced_content}}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = MetaLLMProvider(api_key="mock-key", client=client)

    result = await provider.generate_note("Fenced Note", "article", "Body text")
    assert result.is_success
    assert result.structured_output is not None
    assert result.structured_output.overview == "Overview from markdown fenced response."


@pytest.mark.anyio
async def test_malformed_json_returns_schema_validation_failed() -> None:
    """Verify malformed JSON from provider returns controlled schema_validation_failed error."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "This is not valid JSON at all."}}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = MetaLLMProvider(api_key="mock-key", client=client)

    result = await provider.generate_note("Malformed", "video", "Transcript text")
    assert not result.is_success
    assert result.error_category == "schema_validation_failed"


@pytest.mark.anyio
async def test_missing_required_fields_in_json_rejected() -> None:
    """Verify JSON lacking required overview or key_points is rejected by schema validator."""
    invalid_schema_json = {
        "overview": "Overview is here",
        # missing key_points entirely
        "links": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(invalid_schema_json)}}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = MetaLLMProvider(api_key="mock-key", client=client)

    result = await provider.generate_note("Missing Fields", "article", "Content")
    assert not result.is_success
    assert result.error_category == "schema_validation_failed"


def test_link_item_validates_url_scheme_and_hostname() -> None:
    """Verify LinkItem strictly accepts only http and https URLs with valid hostnames."""
    # Valid
    item = LinkItem(url="https://example.com/docs", anchor_text="Documentation")
    assert item.url == "https://example.com/docs"

    # Reject javascript:
    with pytest.raises(ValueError, match="scheme must be http or https"):
        LinkItem(url="javascript:alert(1)", anchor_text="XSS")

    # Reject empty URL
    with pytest.raises(ValueError, match="cannot be empty"):
        LinkItem(url="", anchor_text="Empty")

    # Reject missing host
    with pytest.raises(ValueError, match="missing hostname"):
        LinkItem(url="https://", anchor_text="No host")


@pytest.mark.anyio
@pytest.mark.parametrize("status,expected_category", [
    (401, "auth_failed"),
    (403, "forbidden"),
    (422, "validation_error"),
    (429, "rate_limited"),
])
async def test_non_retryable_http_errors(status: int, expected_category: str) -> None:
    """Verify 401, 403, 422, 429 return immediately without multiple retry attempts."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(status, text=f"Error {status}")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = MetaLLMProvider(api_key="mock-key", client=client)

    result = await provider.generate_note("Error Test", "article", "Content")
    assert not result.is_success
    assert result.error_category == expected_category
    assert call_count == 1  # Exactly 1 call, zero retries


@pytest.mark.anyio
async def test_transient_500_retries_and_succeeds() -> None:
    """Verify transient 500 error retries and succeeds on subsequent attempt."""
    call_count = 0
    sample_json = {
        "overview": "Overview after retry.",
        "key_points": ["First point."],
        "links": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(502, text="Bad Gateway")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(sample_json)}}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = MetaLLMProvider(api_key="mock-key", client=client)

    with patch("asyncio.sleep", return_value=None):
        result = await provider.generate_note("Retry Test", "article", "Content")

    assert result.is_success
    assert call_count == 2
    assert result.structured_output is not None
    assert result.structured_output.overview == "Overview after retry."


@pytest.mark.anyio
async def test_persistent_500_reaches_retry_limit() -> None:
    """Verify persistent 500 error stops at MAX_TRANSIENT_RETRIES (3 attempts total)."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(503, text="Service Unavailable")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = MetaLLMProvider(api_key="mock-key", client=client)

    with patch("asyncio.sleep", return_value=None):
        result = await provider.generate_note("Persistent 503", "article", "Content")

    assert not result.is_success
    assert result.error_category == "server_error"
    assert call_count == 3  # initial + 2 retries


@pytest.mark.anyio
async def test_read_timeout_handled_cleanly() -> None:
    """Verify httpx.ReadTimeout returns controlled timeout error category."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Socket timed out")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = MetaLLMProvider(api_key="mock-key", client=client)

    result = await provider.generate_note("Timeout Test", "article", "Content")
    assert not result.is_success
    assert result.error_category == "timeout"
