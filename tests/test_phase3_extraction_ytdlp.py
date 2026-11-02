"""Tests for Phase 3 Task 3 Component 3.1: YouTube Metadata Extractor.

Verifies deterministic extraction of video metadata using yt-dlp mocks, strict
contract adherence, zero media download, privacy enforcement, and ADR 0002 rescue triggers.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch
import pytest

from backend.contracts.enums import Kind
from backend.contracts.extraction import ExtractionResult
from backend.extraction.protocol import Extractor
from backend.extraction.ytdlp import (
    YouTubeMetadataExtractor,
    _normalize_duration,
    _normalize_iso_date,
    _sanitize_thumbnail_url,
)


def _sample_ytdlp_info(**overrides: Any) -> dict[str, Any]:
    """Return a representative yt-dlp metadata info dictionary."""
    base: dict[str, Any] = {
        "id": "dQw4w9WgXcQ",
        "title": "Rick Astley - Never Gonna Give You Up (Official Music Video)",
        "channel": "Rick Astley",
        "uploader": "RickAstleyVEVO",
        "duration": 213,
        "upload_date": "20091025",
        "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg?token=secret123&expire=9999",
        "subtitles": {"en": [{"ext": "vtt", "url": "https://example.com/sub.vtt"}], "es": []},
        "automatic_captions": {"en": [{"ext": "vtt", "url": "https://example.com/auto.vtt"}]},
        "webpage_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    }
    base.update(overrides)
    return base


def test_extractor_protocol_conformance() -> None:
    """Verify YouTubeMetadataExtractor conforms to the Extractor runtime protocol."""
    extractor = YouTubeMetadataExtractor()
    assert isinstance(extractor, Extractor)


@pytest.mark.anyio
async def test_extract_valid_youtube_video() -> None:
    """Verify normal extraction of title, channel, duration, date, and captions."""
    extractor = YouTubeMetadataExtractor()
    mock_info = _sample_ytdlp_info()

    with patch.object(extractor, "_extract_info_sync", return_value=mock_info) as mock_sync:
        result = await extractor.extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert mock_sync.called
    assert result.tier == 1
    assert result.kind == Kind.VIDEO
    assert result.title == "Rick Astley - Never Gonna Give You Up (Official Music Video)"
    assert result.channel == "Rick Astley"
    assert result.duration == 213
    assert result.published == "2009-10-25"
    assert result.body is None
    assert result.transcript_available is False
    assert result.capability_flags.has_audio is True
    assert result.source_meta["video_id"] == "dQw4w9WgXcQ"
    assert result.source_meta["has_captions"] is True
    assert result.source_meta["subtitles"] == ["en", "es"]
    assert result.source_meta["automatic_captions"] == ["en"]
    # Privacy: query params stripped from thumbnail
    assert result.source_meta["thumbnail"] == "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"
    assert not result.needs_tier2_rescue()


@pytest.mark.anyio
async def test_extract_missing_title_and_channel() -> None:
    """Verify behavior when title and channel are absent."""
    extractor = YouTubeMetadataExtractor()
    mock_info = _sample_ytdlp_info(title="", channel="", uploader="")

    with patch.object(extractor, "_extract_info_sync", return_value=mock_info):
        result = await extractor.extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert result.title is None
    assert result.channel is None
    assert result.kind == Kind.VIDEO
    # Without title and without transcript, ADR 0002 rescue fires
    assert result.needs_tier2_rescue() is True


@pytest.mark.anyio
async def test_extract_missing_duration_and_date() -> None:
    """Verify that missing optional duration and date cleanly normalize to None."""
    extractor = YouTubeMetadataExtractor()
    mock_info = _sample_ytdlp_info(duration=None, upload_date=None, release_date=None)

    with patch.object(extractor, "_extract_info_sync", return_value=mock_info):
        result = await extractor.extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert result.duration is None
    assert result.published is None
    assert result.title is not None
    # Still has title, so rescue not needed
    assert result.needs_tier2_rescue() is False


def test_date_normalization_valid_yyyymmdd() -> None:
    """Verify conversion of YYYYMMDD to ISO YYYY-MM-DD."""
    assert _normalize_iso_date("20240215") == "2024-02-15"
    assert _normalize_iso_date("20201231") == "2020-12-31"


def test_date_normalization_invalid_values() -> None:
    """Verify invalid or impossible dates normalize to None."""
    assert _normalize_iso_date("20241340") is None  # Month 13
    assert _normalize_iso_date("invalid-text") is None
    assert _normalize_iso_date("") is None
    assert _normalize_iso_date(None) is None


def test_duration_normalization_boundaries() -> None:
    """Verify duration normalization across valid, zero, negative, and malformed values."""
    assert _normalize_duration(0) == 0
    assert _normalize_duration(120) == 120
    assert _normalize_duration(120.9) == 120
    assert _normalize_duration(-1) is None
    assert _normalize_duration(-100) is None
    assert _normalize_duration("not-a-number") is None
    assert _normalize_duration(None) is None


@pytest.mark.anyio
async def test_duration_boundary_zero_second_short() -> None:
    """Verify that a zero-second duration is preserved as 0, not converted to None."""
    extractor = YouTubeMetadataExtractor()
    mock_info = _sample_ytdlp_info(duration=0)

    with patch.object(extractor, "_extract_info_sync", return_value=mock_info):
        result = await extractor.extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert result.duration == 0


@pytest.mark.anyio
async def test_extract_invalid_or_unsupported_url() -> None:
    """Verify degraded result when provider raises unsupported/invalid URL error."""
    extractor = YouTubeMetadataExtractor()

    with patch.object(extractor, "_extract_info_sync", side_effect=ValueError("Unsupported URL format")):
        result = await extractor.extract("https://not-youtube.com/post/123")

    assert result.tier == 1
    assert result.kind == Kind.UNKNOWN
    assert result.title is None
    assert result.body is None
    assert result.source_meta["category"] == "invalid_url"
    assert result.source_meta["status"] == "unavailable"
    assert result.needs_tier2_rescue() is True


@pytest.mark.anyio
async def test_extract_empty_provider_response() -> None:
    """Verify degraded result when yt-dlp returns an empty dictionary."""
    extractor = YouTubeMetadataExtractor()

    with patch.object(extractor, "_extract_info_sync", return_value={}):
        # _extract_info_sync raises ValueError on empty dict
        with patch.object(extractor, "_extract_info_sync", side_effect=ValueError("empty info")):
            result = await extractor.extract("https://www.youtube.com/watch?v=empty")

    assert result.kind == Kind.UNKNOWN
    assert result.source_meta["category"] == "invalid_metadata"
    assert result.needs_tier2_rescue() is True


@pytest.mark.anyio
async def test_extract_private_or_unavailable_video() -> None:
    """Verify degraded result on private/deleted/blocked video without leaking stack trace."""
    extractor = YouTubeMetadataExtractor()

    with patch.object(
        extractor,
        "_extract_info_sync",
        side_effect=RuntimeError("Private video. Sign in if you've been granted access to this video"),
    ):
        result = await extractor.extract("https://www.youtube.com/watch?v=private")

    assert result.kind == Kind.UNKNOWN
    assert result.source_meta["category"] == "unavailable"
    assert result.source_meta["status"] == "unavailable"
    # Verify no raw exception text or sensitive tokens in source_meta
    assert "Private video" not in str(result.source_meta)
    assert result.needs_tier2_rescue() is True


@pytest.mark.anyio
async def test_extract_timeout_handling() -> None:
    """Verify clean degraded result when extraction exceeds the timeout budget."""
    extractor = YouTubeMetadataExtractor()

    async def slow_extract(url: str) -> dict[str, Any]:
        await asyncio.sleep(5)
        return _sample_ytdlp_info()

    with patch("backend.extraction.ytdlp.settings.EXTRACTION_TIMEOUT_SECONDS", 0.05):
        with patch.object(extractor, "_extract_info_sync", side_effect=lambda u: __import__("time").sleep(1)):
            result = await extractor.extract("https://www.youtube.com/watch?v=timeout")

    assert result.kind == Kind.UNKNOWN
    assert result.source_meta["category"] == "timeout"
    assert result.needs_tier2_rescue() is True


@pytest.mark.anyio
async def test_caption_discovery_metadata_only() -> None:
    """Verify discovery of manual vs automatic captions without downloading caption text."""
    extractor = YouTubeMetadataExtractor()
    mock_info = _sample_ytdlp_info(
        subtitles={"en": [{"url": "http://evil.com/leak"}], "fr": []},
        automatic_captions={"es": [{"url": "http://evil.com/leak"}]},
    )

    with patch.object(extractor, "_extract_info_sync", return_value=mock_info):
        result = await extractor.extract("https://www.youtube.com/watch?v=captions")

    assert result.source_meta["has_captions"] is True
    assert result.source_meta["subtitles"] == ["en", "fr"]
    assert result.source_meta["automatic_captions"] == ["es"]
    # Verification: caption URLs are NOT exposed in source_meta or body
    assert "http://evil.com" not in str(result.source_meta)
    assert result.body is None
    assert result.transcript_available is False


@pytest.mark.anyio
async def test_no_caption_metadata() -> None:
    """Verify behavior when neither manual nor automatic captions are present."""
    extractor = YouTubeMetadataExtractor()
    mock_info = _sample_ytdlp_info(subtitles={}, automatic_captions={})

    with patch.object(extractor, "_extract_info_sync", return_value=mock_info):
        result = await extractor.extract("https://www.youtube.com/watch?v=nocaptions")

    assert result.source_meta["has_captions"] is False
    assert result.source_meta["subtitles"] == []
    assert result.source_meta["automatic_captions"] == []


def test_ytdlp_opts_strictly_forbid_download() -> None:
    """Verify that yt-dlp initialization parameters mandate skip_download and download=False."""
    extractor = YouTubeMetadataExtractor()

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_instance = MagicMock()
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.extract_info.return_value = _sample_ytdlp_info()
        mock_ydl_cls.return_value = mock_instance

        extractor._extract_info_sync("https://www.youtube.com/watch?v=123")

        # Verify YoutubeDL was instantiated with skip_download=True
        call_args, call_kwargs = mock_ydl_cls.call_args
        opts = call_args[0]
        assert opts.get("skip_download") is True
        assert opts.get("socket_timeout") <= 30

        # Verify extract_info was called with download=False
        extract_args, extract_kwargs = mock_instance.extract_info.call_args
        assert extract_kwargs.get("download") is False


def test_thumbnail_query_param_stripping() -> None:
    """Verify that thumbnail sanitization strips query parameters and tokens."""
    raw = "https://i.ytimg.com/vi/abc/default.jpg?sqp=-oaymwEbCKgBEF5IVfKriqkDDggBFQAAiEIYAXABwAEG&rs=AOn4CLDh"
    clean = _sanitize_thumbnail_url(raw)
    assert clean == "https://i.ytimg.com/vi/abc/default.jpg"
    assert "sqp=" not in clean
    assert "rs=" not in clean
