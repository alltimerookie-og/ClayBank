"""Caption discovery, retrieval, and parsing for video extraction (ADR 0002, ADR 0004).

Retrieves and normalizes WebVTT, JSON, and XML caption tracks into clean plain text
without downloading video/audio media or persisting temporary files.
"""
from __future__ import annotations

import html
import json
import logging
import re
from typing import Any
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import httpx

from backend.contracts.extraction import ExtractionResult
from backend.extraction.transport import (
    MAX_REDIRECTS,
    create_ssrf_protected_client,
    validate_url_security,
)

logger = logging.getLogger(__name__)

# Bounded caption response size: 500 KB limit
MAX_CAPTION_SIZE_BYTES = 512_000
HTTP_CONNECT_TIMEOUT_SECONDS = 5.0
HTTP_READ_TIMEOUT_SECONDS = 10.0


def parse_vtt(content: str) -> str:
    """Parse WebVTT content into clean normalized plain text without timestamps or cue tags.

    Args:
        content: Raw WebVTT file content.

    Returns:
        str: Normalized plain-text transcript.
    """
    if not content or not content.strip():
        return ""

    lines = content.splitlines()
    text_blocks: list[str] = []

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        # Skip header lines, comments, and cues
        if (
            line_clean.startswith("WEBVTT")
            or line_clean.startswith("NOTE")
            or line_clean.startswith("Kind:")
            or line_clean.startswith("Language:")
            or "-->" in line_clean
        ):
            continue
        # Skip numeric cue identifiers
        if line_clean.isdigit():
            continue

        # Strip HTML/VTT formatting tags e.g. <c>, </c>, <v Speaker>, <b>, etc.
        text = re.sub(r"<[^>]+>", "", line_clean).strip()
        if not text:
            continue

        # Deduplicate immediate identical lines (common in rolling auto-captions)
        if text_blocks and text_blocks[-1] == text:
            continue
        text_blocks.append(text)

    # Join lines and collapse excess whitespace
    joined = " ".join(text_blocks)
    return re.sub(r"\s+", " ", joined).strip()


def parse_json_captions(content: str) -> str:
    """Parse YouTube JSON3 timedtext format into normalized plain text.

    Args:
        content: Raw JSON string from timedtext endpoint.

    Returns:
        str: Normalized plain-text transcript.
    """
    if not content or not content.strip():
        return ""

    try:
        data = json.loads(content)
    except Exception:
        return ""

    if not isinstance(data, dict):
        return ""

    text_parts: list[str] = []
    events = data.get("events", [])
    if not isinstance(events, list):
        return ""

    for ev in events:
        if not isinstance(ev, dict):
            continue
        segs = ev.get("segs", [])
        if not isinstance(segs, list):
            continue
        for seg in segs:
            if not isinstance(seg, dict):
                continue
            utf8 = seg.get("utf8", "")
            if isinstance(utf8, str) and utf8.strip() and utf8 != "\n":
                text_parts.append(utf8.strip())

    joined = " ".join(text_parts)
    return re.sub(r"\s+", " ", joined).strip()


def parse_xml_captions(content: str) -> str:
    """Parse XML timedtext format (<transcript><text>...</text></transcript>) safely.

    Args:
        content: Raw XML string from timedtext endpoint.

    Returns:
        str: Normalized plain-text transcript.
    """
    if not content or not content.strip():
        return ""

    try:
        # Standard ElementTree in Python 3.12 does not resolve external entities (safe from XXE)
        root = ET.fromstring(content)
    except Exception:
        return ""

    parts: list[str] = []
    for elem in root.iter():
        if elem.tag in ("text", "p", "s") and elem.text:
            cleaned = html.unescape(elem.text.strip())
            if cleaned:
                parts.append(cleaned)

    joined = " ".join(parts)
    return re.sub(r"\s+", " ", joined).strip()


def parse_caption_content(content: str, format_hint: str = "") -> str:
    """Detect and parse caption content into normalized plain text.

    Args:
        content: Raw caption file body.
        format_hint: Optional format extension or name (e.g. 'vtt', 'json3', 'srv1').

    Returns:
        str: Normalized plain-text transcript.
    """
    stripped = content.strip()
    hint = format_hint.lower()

    if "vtt" in hint or stripped.startswith("WEBVTT"):
        return parse_vtt(content)
    if "json" in hint or (stripped.startswith("{") and stripped.endswith("}")):
        return parse_json_captions(content)
    if "xml" in hint or "srv" in hint or (stripped.startswith("<") and stripped.endswith(">")):
        return parse_xml_captions(content)

    # Fallback attempt by heuristic sniffing
    if stripped.startswith("WEBVTT"):
        return parse_vtt(content)
    if stripped.startswith("{"):
        return parse_json_captions(content)
    if stripped.startswith("<"):
        return parse_xml_captions(content)

    return ""


def select_caption_track(info: dict[str, Any], preferred_lang: str = "en") -> dict[str, Any] | None:
    """Select the best available caption track (preferring manual subtitles over automatic captions).

    Args:
        info: yt-dlp metadata info dictionary.
        preferred_lang: Preferred language code prefix (defaults to 'en').

    Returns:
        dict[str, Any] | None: Dictionary with 'url', 'ext', 'lang', and 'type', or None if unavailable.
    """
    subtitles = info.get("subtitles") or {}
    auto_captions = info.get("automatic_captions") or {}

    # Category preference: manual subtitles first, then automatic captions
    categories = [("manual", subtitles), ("automatic", auto_captions)]

    for cat_name, cat_dict in categories:
        if not isinstance(cat_dict, dict) or not cat_dict:
            continue

        available_langs = list(cat_dict.keys())
        chosen_lang: str | None = None

        # 1. Exact match for preferred language
        if preferred_lang in cat_dict:
            chosen_lang = preferred_lang
        else:
            # 2. Prefix match (e.g. 'en-US', 'en-orig')
            for lang in available_langs:
                if lang.startswith(preferred_lang):
                    chosen_lang = lang
                    break
            # 3. Fallback to first available language
            if not chosen_lang and available_langs:
                chosen_lang = available_langs[0]

        if not chosen_lang:
            continue

        formats = cat_dict.get(chosen_lang)
        if not isinstance(formats, list) or not formats:
            continue

        # Format preference: vtt > json3 > xml/srv
        chosen_format: dict[str, Any] | None = None
        for fmt in formats:
            if not isinstance(fmt, dict) or not fmt.get("url"):
                continue
            ext = (fmt.get("ext") or "").lower()
            if ext == "vtt":
                chosen_format = fmt
                break
            if ext in ("json3", "json") and not chosen_format:
                chosen_format = fmt
            elif ext in ("srv1", "srv2", "srv3", "xml") and not chosen_format:
                chosen_format = fmt

        # If none matched priority extensions, pick first format with a URL
        if not chosen_format:
            for fmt in formats:
                if isinstance(fmt, dict) and fmt.get("url"):
                    chosen_format = fmt
                    break

        if chosen_format:
            return {
                "url": chosen_format["url"],
                "ext": (chosen_format.get("ext") or "vtt").lower(),
                "lang": chosen_lang,
                "type": cat_name,
            }

    return None


class CaptionRetriever:
    """Retrieves and parses remote caption tracks with strict privacy and resource limits."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def retrieve_and_parse(self, track: dict[str, Any]) -> str | None:
        """Download and parse a caption track into clean plain text.

        Args:
            track: Track dictionary with 'url' and 'ext'.

        Returns:
            str | None: Normalized transcript, or None if retrieval/parsing failed or yielded no text.
        """
        url = track.get("url")
        if not url or not isinstance(url, str):
            return None

        # Enforce scheme and security checks (SSRF, private networks, cloud metadata)
        is_safe, sec_cat = validate_url_security(url)
        if not is_safe:
            logger.warning("Caption track URL failed security check: %s (reason=%s)", url, sec_cat)
            return None

        fmt = track.get("ext", "")

        try:
            if self._client is not None:
                content = await self._fetch(self._client, url)
            else:
                async with create_ssrf_protected_client(
                    timeout=httpx.Timeout(
                        connect=HTTP_CONNECT_TIMEOUT_SECONDS,
                        read=HTTP_READ_TIMEOUT_SECONDS,
                        write=5.0,
                        pool=5.0,
                    )
                ) as client:
                    content = await self._fetch(client, url)

            if not content:
                return None

            parsed_text = parse_caption_content(content, format_hint=fmt)
            return parsed_text if parsed_text else None

        except Exception as err:
            logger.warning("Caption retrieval failed: category=%s", type(err).__name__)
            return None

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> str | None:
        """Fetch caption URL with streaming size enforcement and manual redirect validation."""
        current_url = url
        visited_urls: set[str] = {current_url}
        redirect_count = 0

        while True:
            is_safe, sec_cat = validate_url_security(current_url)
            if not is_safe:
                logger.warning("Caption URL failed security validation: %s", sec_cat)
                return None

            try:
                async with client.stream("GET", current_url) as resp:
                    if resp.status_code in (301, 302, 303, 307, 308):
                        redirect_count += 1
                        if redirect_count > MAX_REDIRECTS:
                            logger.warning("Caption retrieval exceeded redirect limit (%d)", MAX_REDIRECTS)
                            return None

                        location = resp.headers.get("location")
                        if not location:
                            logger.warning("Caption redirect missing location header")
                            return None

                        next_url = urljoin(current_url, location)
                        if next_url in visited_urls:
                            logger.warning("Caption redirect loop detected: %s", next_url)
                            return None

                        visited_urls.add(next_url)
                        is_safe_next, sec_cat_next = validate_url_security(next_url)
                        if not is_safe_next:
                            logger.warning("Caption redirect target is unsafe: %s (%s)", next_url, sec_cat_next)
                            return None

                        current_url = next_url
                        continue

                    if resp.status_code != 200:
                        logger.warning("Caption retrieval received HTTP %d", resp.status_code)
                        return None

                    cl_header = resp.headers.get("content-length")
                    if cl_header:
                        try:
                            if int(cl_header) > MAX_CAPTION_SIZE_BYTES:
                                logger.warning("Caption response header indicates size > cap (%s bytes)", cl_header)
                                return None
                        except ValueError:
                            pass

                    body_chunks: list[bytes] = []
                    total_bytes = 0
                    oversized = False

                    async for chunk in resp.aiter_bytes(chunk_size=4096):
                        total_bytes += len(chunk)
                        if total_bytes > MAX_CAPTION_SIZE_BYTES:
                            oversized = True
                            break
                        body_chunks.append(chunk)

                    if oversized:
                        logger.warning("Caption response exceeded size cap (%d bytes) during streaming", total_bytes)
                        return None

                    raw_bytes = b"".join(body_chunks)
                    return raw_bytes.decode("utf-8", errors="replace")

            except Exception as err:
                logger.warning("Caption streaming fetch failed: %s", type(err).__name__)
                return None


async def enrich_result_with_captions(
    result: ExtractionResult,
    info: dict[str, Any],
    client: httpx.AsyncClient | None = None,
    preferred_lang: str = "en",
) -> ExtractionResult:
    """Enrich an existing ExtractionResult with retrieved and parsed transcript text.

    Args:
        result: Initial ExtractionResult from YouTubeMetadataExtractor.
        info: Raw yt-dlp metadata info dictionary.
        client: Optional httpx.AsyncClient for HTTP requests.
        preferred_lang: Preferred caption language code (defaults to 'en').

    Returns:
        ExtractionResult: Enriched result with body and transcript_available updated.
    """
    track = select_caption_track(info, preferred_lang=preferred_lang)
    if not track:
        return result

    retriever = CaptionRetriever(client=client)
    transcript = await retriever.retrieve_and_parse(track)

    if not transcript:
        return result

    # Update source_meta with selected caption language and type
    updated_meta = dict(result.source_meta)
    updated_meta["caption_language"] = track["lang"]
    updated_meta["caption_type"] = track["type"]

    return ExtractionResult(
        tier=result.tier,
        kind=result.kind,
        title=result.title,
        channel=result.channel,
        duration=result.duration,
        published=result.published,
        body=transcript,
        transcript_available=True,
        capability_flags=result.capability_flags,
        source_meta=updated_meta,
    )
