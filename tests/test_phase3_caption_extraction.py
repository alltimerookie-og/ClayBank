"""Tests for Phase 3 Task 3 Component 3.2: Caption Retrieval and Parsing.

Verifies caption discovery, format parsing (WebVTT, JSON, XML), HTTP error handling,
bounded size enforcement, privacy protections, and ExtractionResult enrichment.
"""
from __future__ import annotations

import json
from typing import Any
import httpx
import pytest

from backend.contracts.enums import Kind
from backend.contracts.extraction import CapabilityFlags, ExtractionResult
from backend.extraction.captions import (
    CaptionRetriever,
    enrich_result_with_captions,
    parse_caption_content,
    parse_json_captions,
    parse_vtt,
    parse_xml_captions,
    select_caption_track,
)


def _base_video_result(**overrides: Any) -> ExtractionResult:
    base = {
        "tier": 1,
        "kind": Kind.VIDEO,
        "title": "Sample Video Title",
        "channel": "Sample Creator",
        "duration": 180,
        "published": "2024-01-01",
        "body": None,
        "transcript_available": False,
        "capability_flags": CapabilityFlags(has_audio=True, has_timeline=False, has_images=False),
        "source_meta": {"video_id": "test1234"},
    }
    base.update(overrides)
    return ExtractionResult(**base)


# ---------------------------------------------------------------------------
# Caption Discovery & Selection Tests
# ---------------------------------------------------------------------------


def test_select_caption_track_manual_preferred_over_auto() -> None:
    """Verify that manual subtitles are selected over automatic captions."""
    info = {
        "subtitles": {"en": [{"ext": "vtt", "url": "https://example.com/manual_en.vtt"}]},
        "automatic_captions": {"en": [{"ext": "vtt", "url": "https://example.com/auto_en.vtt"}]},
    }
    track = select_caption_track(info, preferred_lang="en")
    assert track is not None
    assert track["type"] == "manual"
    assert track["url"] == "https://example.com/manual_en.vtt"
    assert track["lang"] == "en"


def test_select_caption_track_auto_fallback_when_no_manual() -> None:
    """Verify fallback to automatic captions when manual subtitles are missing."""
    info = {
        "subtitles": {},
        "automatic_captions": {"en": [{"ext": "vtt", "url": "https://example.com/auto_en.vtt"}]},
    }
    track = select_caption_track(info, preferred_lang="en")
    assert track is not None
    assert track["type"] == "automatic"
    assert track["url"] == "https://example.com/auto_en.vtt"


def test_select_caption_track_multiple_languages() -> None:
    """Verify language selection with preferred language vs available languages."""
    info = {
        "subtitles": {
            "es": [{"ext": "vtt", "url": "https://example.com/es.vtt"}],
            "fr": [{"ext": "vtt", "url": "https://example.com/fr.vtt"}],
        }
    }
    # No English, should fall back to first available (es)
    track = select_caption_track(info, preferred_lang="en")
    assert track is not None
    assert track["lang"] == "es"

    # Explicit French preference
    track_fr = select_caption_track(info, preferred_lang="fr")
    assert track_fr is not None
    assert track_fr["lang"] == "fr"


def test_select_caption_track_no_metadata_or_empty() -> None:
    """Verify behavior when no subtitles or automatic captions exist."""
    assert select_caption_track({}) is None
    assert select_caption_track({"subtitles": {}, "automatic_captions": {}}) is None


def test_select_caption_track_missing_url() -> None:
    """Verify tracks missing URLs are skipped."""
    info = {
        "subtitles": {
            "en": [{"ext": "vtt"}],  # No url key
        }
    }
    assert select_caption_track(info) is None


# ---------------------------------------------------------------------------
# Format Parsing Tests (WebVTT, JSON, XML)
# ---------------------------------------------------------------------------


def test_parse_vtt_normal_and_multiline() -> None:
    """Verify WebVTT parsing strips timestamps, cue tags, and joins multiline text."""
    vtt = """WEBVTT
Kind: captions
Language: en

00:00:01.000 --> 00:00:03.000
<c.color>Welcome to</c> ClayBank

2
00:00:03.500 --> 00:00:06.000
This is a multiline
caption block.
"""
    parsed = parse_vtt(vtt)
    assert parsed == "Welcome to ClayBank This is a multiline caption block."


def test_parse_vtt_empty_or_whitespace() -> None:
    """Verify empty or header-only WebVTT returns empty string."""
    assert parse_vtt("") == ""
    assert parse_vtt("   \n\n  ") == ""
    assert parse_vtt("WEBVTT\n\n") == ""


def test_parse_vtt_malformed_cues() -> None:
    """Verify malformed WebVTT cues recover and extract readable text."""
    malformed = """WEBVTT
not-a-timestamp
Just raw text in a malformed line
00:00 --> invalid
Valid trailing text.
"""
    parsed = parse_vtt(malformed)
    assert "Just raw text" in parsed
    assert "Valid trailing text." in parsed


def test_parse_vtt_deduplicates_rolling_captions() -> None:
    """Verify that repeated consecutive lines common in auto-captions are deduplicated."""
    vtt = """WEBVTT

00:00:01.000 --> 00:00:02.000
The quick brown fox

00:00:02.000 --> 00:00:03.000
The quick brown fox
jumps over the lazy dog
"""
    parsed = parse_vtt(vtt)
    assert parsed == "The quick brown fox jumps over the lazy dog"


def test_parse_json_captions_success() -> None:
    """Verify YouTube JSON3 timedtext structure parses to plain text."""
    payload = json.dumps({
        "events": [
            {"tStartMs": 1000, "dDurationMs": 2000, "segs": [{"utf8": "First sentence. "}]},
            {"tStartMs": 3000, "dDurationMs": 1500, "segs": [{"utf8": "Second "}, {"utf8": "sentence."}]},
        ]
    })
    parsed = parse_json_captions(payload)
    assert parsed == "First sentence. Second sentence."


def test_parse_json_captions_malformed() -> None:
    """Verify malformed JSON returns empty string safely."""
    assert parse_json_captions("{not-valid-json}") == ""
    assert parse_json_captions(json.dumps({"events": "not-a-list"})) == ""
    assert parse_json_captions("") == ""


def test_parse_xml_captions_success() -> None:
    """Verify XML timedtext parses tags and unescapes entities."""
    xml_data = """<?xml version="1.0" encoding="utf-8" ?>
<transcript>
  <text start="0.5" dur="1.5">Welcome &amp; hello,</text>
  <text start="2.0" dur="2.0">&lt;viewer&gt;!</text>
</transcript>
"""
    parsed = parse_xml_captions(xml_data)
    assert parsed == "Welcome & hello, <viewer>!"


def test_parse_xml_captions_malformed() -> None:
    """Verify malformed XML returns empty string safely."""
    assert parse_xml_captions("<transcript><unclosed>") == ""
    assert parse_xml_captions("") == ""


def test_parse_caption_content_sniffer() -> None:
    """Verify automatic format sniffing when hint is omitted."""
    assert parse_caption_content("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello") == "Hello"
    assert parse_caption_content('{"events": [{"segs": [{"utf8": "JSON"}]}]}') == "JSON"
    assert parse_caption_content("<transcript><text>XML</text></transcript>") == "XML"
    assert parse_caption_content("plain text with no format") == ""


# ---------------------------------------------------------------------------
# HTTP Retrieval & Error Handling Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_caption_retriever_successful_vtt() -> None:
    """Verify CaptionRetriever fetches and parses a remote WebVTT track."""
    vtt_content = b"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nRetrieved transcript."

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=vtt_content)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        retriever = CaptionRetriever(client=client)
        text = await retriever.retrieve_and_parse({"url": "https://example.com/sub.vtt", "ext": "vtt"})

    assert text == "Retrieved transcript."


@pytest.mark.anyio
@pytest.mark.parametrize("status_code", [403, 404, 429, 500, 503])
async def test_caption_retriever_http_errors(status_code: int) -> None:
    """Verify graceful None return on various HTTP error statuses."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text="Error")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        retriever = CaptionRetriever(client=client)
        text = await retriever.retrieve_and_parse({"url": "https://example.com/sub.vtt", "ext": "vtt"})

    assert text is None


@pytest.mark.anyio
async def test_caption_retriever_connection_error() -> None:
    """Verify graceful None return on network connection failure."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Network unreachable")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        retriever = CaptionRetriever(client=client)
        text = await retriever.retrieve_and_parse({"url": "https://example.com/sub.vtt", "ext": "vtt"})

    assert text is None


@pytest.mark.anyio
async def test_caption_retriever_timeout() -> None:
    """Verify graceful None return on request timeout."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Read timed out")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        retriever = CaptionRetriever(client=client)
        text = await retriever.retrieve_and_parse({"url": "https://example.com/sub.vtt", "ext": "vtt"})

    assert text is None


@pytest.mark.anyio
async def test_caption_retriever_oversized_response() -> None:
    """Verify responses exceeding 512 KB are rejected to prevent memory exhaustion."""
    oversized = b"WEBVTT\n\n" + (b"00:00:01.000 --> 00:00:02.000\nSome word\n\n" * 20000)
    assert len(oversized) > 512_000

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=oversized)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        retriever = CaptionRetriever(client=client)
        text = await retriever.retrieve_and_parse({"url": "https://example.com/large.vtt", "ext": "vtt"})

    assert text is None


# ---------------------------------------------------------------------------
# ExtractionResult Enrichment Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_enrich_result_with_captions_success() -> None:
    """Verify ExtractionResult is enriched with body, flag, and language metadata."""
    vtt_content = b"WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nEnriched transcript body."
    info = {
        "subtitles": {"en": [{"ext": "vtt", "url": "https://example.com/captions.vtt"}]}
    }
    initial_result = _base_video_result()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=vtt_content)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        enriched = await enrich_result_with_captions(initial_result, info, client=client)

    assert enriched.body == "Enriched transcript body."
    assert enriched.transcript_available is True
    assert enriched.source_meta["caption_language"] == "en"
    assert enriched.source_meta["caption_type"] == "manual"
    assert enriched.title == initial_result.title
    assert enriched.duration == initial_result.duration
    assert not enriched.needs_tier2_rescue()


@pytest.mark.anyio
async def test_enrich_result_with_captions_failure_preserves_metadata() -> None:
    """Verify failed caption retrieval preserves original metadata without crashing."""
    info = {
        "subtitles": {"en": [{"ext": "vtt", "url": "https://example.com/error.vtt"}]}
    }
    initial_result = _base_video_result(title="Preserved Title")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Not Found")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        enriched = await enrich_result_with_captions(initial_result, info, client=client)

    assert enriched.body is None
    assert enriched.transcript_available is False
    assert enriched.title == "Preserved Title"
    assert "caption_language" not in enriched.source_meta
    # Because title exists, rescue is not needed
    assert not enriched.needs_tier2_rescue()
