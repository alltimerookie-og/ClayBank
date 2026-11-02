"""YouTube metadata extractor using yt-dlp (ADR 0002, ADR 0004).

Extracts video metadata without downloading video or audio content.
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import re
from typing import Any, cast
from urllib.parse import urlparse

from backend.config import settings
from backend.contracts.enums import Kind
from backend.contracts.extraction import CapabilityFlags, ExtractionResult

logger = logging.getLogger(__name__)

_DATE_YYYYMMDD_PATTERN = re.compile(r"^(\d{4})(\d{2})(\d{2})$")


def _sanitize_thumbnail_url(raw_url: Any) -> str | None:
    """Sanitize thumbnail URL by stripping query parameters that might carry tokens."""
    if not raw_url or not isinstance(raw_url, str):
        return None
    try:
        parsed = urlparse(raw_url.strip())
        if not parsed.scheme or not parsed.netloc:
            return None
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    except Exception:
        return None


def _normalize_iso_date(raw_date: Any) -> str | None:
    """Convert YYYYMMDD or ISO date string into YYYY-MM-DD. Returns None if invalid."""
    if not raw_date or not isinstance(raw_date, str):
        return None
    cleaned = raw_date.strip()
    match = _DATE_YYYYMMDD_PATTERN.match(cleaned)
    if match:
        year, month, day = match.groups()
        candidate = f"{year}-{month}-{day}"
        try:
            datetime.date.fromisoformat(candidate)
            return candidate
        except ValueError:
            return None
    try:
        datetime.date.fromisoformat(cleaned)
        return cleaned
    except ValueError:
        return None


def _normalize_duration(raw_duration: Any) -> int | None:
    """Normalize duration to integer seconds >= 0. Returns None if invalid or negative."""
    if raw_duration is None:
        return None
    try:
        val = int(raw_duration)
        return val if val >= 0 else None
    except (ValueError, TypeError):
        return None


class YouTubeMetadataExtractor:
    """Extracts video metadata from YouTube URLs using yt-dlp without downloading media."""

    async def extract(self, url: str, platform: str = "youtube") -> ExtractionResult:
        """Extract metadata for a video URL without downloading media.

        Args:
            url: The video URL to extract.
            platform: Platform name (defaults to 'youtube').

        Returns:
            ExtractionResult: Populated with video metadata, or degraded to UNKNOWN on failure.
        """
        timeout_seconds = settings.EXTRACTION_TIMEOUT_SECONDS
        try:
            async with asyncio.timeout(timeout_seconds):
                info = await asyncio.to_thread(self._extract_info_sync, url)
                return self._build_result(info)
        except TimeoutError:
            logger.warning(
                "yt-dlp extraction timed out after %ds for platform=%s",
                timeout_seconds,
                platform,
            )
            return ExtractionResult(
                tier=1,
                kind=Kind.UNKNOWN,
                title=None,
                body=None,
                source_meta={"category": "timeout", "status": "unavailable"},
            )
        except Exception as err:
            category = self._categorize_error(err)
            logger.warning(
                "yt-dlp extraction failed for platform=%s category=%s",
                platform,
                category,
            )
            return ExtractionResult(
                tier=1,
                kind=Kind.UNKNOWN,
                title=None,
                body=None,
                source_meta={"category": category, "status": "unavailable"},
            )

    def _extract_info_sync(self, url: str) -> dict[str, Any]:
        """Synchronously execute yt-dlp extract_info with media download strictly disabled."""
        import yt_dlp  # type: ignore[import-untyped]  # yt-dlp lacks inline PEP 561 stubs

        ydl_opts: dict[str, Any] = {
            "skip_download": True,
            "extract_flat": False,
            "quiet": True,
            "no_warnings": True,
            "no_color": True,
            "ignoreerrors": False,
            "socket_timeout": min(15, settings.EXTRACTION_TIMEOUT_SECONDS),
        }
        with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
            raw_info = ydl.extract_info(url, download=False)
            if not raw_info or not isinstance(raw_info, dict):
                raise ValueError("Provider returned empty or invalid metadata dictionary")
            return dict(raw_info)

    def _categorize_error(self, err: Exception) -> str:
        """Categorize exception into a safe, bounded category string."""
        err_msg = str(err).lower()
        if any(term in err_msg for term in ("private", "deleted", "unavailable", "blocked")):
            return "unavailable"
        if any(term in err_msg for term in ("unsupported", "invalid url", "not a valid")):
            return "invalid_url"
        if any(term in err_msg for term in ("empty", "malformed")):
            return "invalid_metadata"
        return "provider_error"

    def _build_result(self, info: dict[str, Any]) -> ExtractionResult:
        """Map raw yt-dlp dictionary into a validated ExtractionResult."""
        title = (info.get("title") or "").strip() or None
        channel = (info.get("channel") or info.get("uploader") or "").strip() or None
        duration = _normalize_duration(info.get("duration"))
        published = _normalize_iso_date(info.get("upload_date") or info.get("release_date"))

        # Extract available caption language codes without downloading caption bodies
        subtitles = sorted(list((info.get("subtitles") or {}).keys()))
        auto_captions = sorted(list((info.get("automatic_captions") or {}).keys()))
        has_captions = bool(subtitles or auto_captions)

        video_id = info.get("id") or None
        clean_thumbnail = _sanitize_thumbnail_url(info.get("thumbnail"))

        source_meta: dict[str, Any] = {
            "video_id": video_id,
            "subtitles": subtitles,
            "automatic_captions": auto_captions,
            "has_captions": has_captions,
        }
        if clean_thumbnail:
            source_meta["thumbnail"] = clean_thumbnail

        return ExtractionResult(
            tier=1,
            kind=Kind.VIDEO,
            title=title,
            channel=channel,
            duration=duration,
            published=published,
            body=None,
            transcript_available=False,
            capability_flags=CapabilityFlags(has_audio=True, has_timeline=False, has_images=False),
            source_meta=source_meta,
        )
