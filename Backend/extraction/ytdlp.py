"""Video extraction provider using yt-dlp metadata and captions."""

from __future__ import annotations

import re
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol
from urllib.parse import urlsplit

from Backend.extraction.result import ExtractionResult, merge_kind

MEDIA_FORMATS = (
    "bv*+ba/b",
    "bv/b",
    "bestaudio/best",
)


@dataclass(frozen=True, slots=True)
class TransientMedia:
    """Transient media outcome with media-type metadata."""

    path: Path | None
    has_video: bool
    has_audio: bool
    kind: str


class VideoMetadata(Protocol):
    """Structural source for deterministic video extraction."""

    def fetch(self, url: str) -> dict:
        """Return provider metadata for one URL."""
        ...


class YtDlpMetadata:
    """yt-dlp metadata source with captions when available."""

    def fetch(self, url: str) -> dict:
        """Fetch metadata before any transient media download."""
        from yt_dlp import YoutubeDL

        options = {
            "quiet": True,
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en"],
            "js_runtimes": {"node": {}},
            "remote_components": {"ejs:github"},
        }
        with YoutubeDL(options) as downloader:
            return downloader.extract_info(url, download=False) or {}


@contextmanager
def transient_media_download(url: str, max_duration_seconds: int = 600) -> Iterator[TransientMedia]:
    """Download video transiently with audio/video/audio-only fallbacks."""
    with tempfile.TemporaryDirectory(prefix="claybank-media-") as directory:
        output = Path(directory) / "source.%(ext)s"
        downloaded: TransientMedia = TransientMedia(None, False, False, "none")
        try:
            from yt_dlp import YoutubeDL

            for media_format in MEDIA_FORMATS:
                options = {
                    "quiet": True,
                    "format": media_format,
                    "outtmpl": str(output),
                    "noplaylist": True,
                    "js_runtimes": {"node": {}},
                    "remote_components": {"ejs:github"},
                }
                try:
                    with YoutubeDL(options) as downloader:
                        info = downloader.extract_info(url, download=True) or {}
                except Exception:
                    continue
                duration = info.get("duration")
                if isinstance(duration, int) and duration > max_duration_seconds:
                    break
                candidates = sorted(Path(directory).glob("source.*"))
                if not candidates:
                    continue
                path = candidates[0]
                has_video = media_format != "bestaudio/best"
                downloaded = TransientMedia(path, has_video, True, "video" if has_video else "audio")
                break
            yield downloaded
        finally:
            for leftover in Path(directory).glob("*"):
                try:
                    leftover.unlink()
                except OSError:
                    pass


class VideoExtractor:
    """Extract tier-1 video metadata into an ExtractionResult."""

    def __init__(self, metadata: VideoMetadata | None = None, allow_transient_media: bool = True) -> None:
        self.metadata = metadata or YtDlpMetadata()
        self.allow_transient_media = allow_transient_media

    def extract(self, url: str) -> ExtractionResult:
        """Return video metadata and optionally verify transient media access."""
        try:
            info = self.metadata.fetch(url)
        except Exception:
            return ExtractionResult(tier=1, kind="unknown")
        title = info.get("title")
        channel = info.get("channel") or info.get("uploader")
        duration = info.get("duration")
        published = self._published(info.get("upload_date"))
        transcript, transcript_available = self._captions(info)
        media = self._transient_media(url) if self.allow_transient_media else None
        media_available = transcript_available or (media is not None and media.has_audio)
        has_video = media.has_video if media else False
        return ExtractionResult(
            tier=1,
            kind=merge_kind("video", title, transcript or ("media" if media_available else None)),
            title=title,
            channel=channel,
            duration=duration if isinstance(duration, int) and duration >= 0 else None,
            published=published,
            body=transcript,
            transcript_available=transcript_available,
            capability_flags={
                "has_audio": media_available,
                "has_timeline": media_available or has_video,
                "has_images": has_video,
            },
            source_meta={"extractor": "yt-dlp", "host": urlsplit(url).hostname},
        )

    def _transient_media(self, url: str) -> TransientMedia | None:
        """Check transient media access without retaining the download."""
        try:
            with transient_media_download(url) as media:
                if media.path is not None and media.path.exists() and media.path.stat().st_size > 0:
                    return media
                return None
        except Exception:
            return None

    @staticmethod
    def _published(upload_date: str | None) -> str | None:
        """Convert YYYYMMDD into YYYY-MM-DD when valid."""
        if upload_date and re.fullmatch(r"\d{8}", upload_date):
            return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
        return None

    @staticmethod
    def _captions(info: dict) -> tuple[str | None, bool]:
        """Return a transcript excerpt from subtitles when present."""
        subtitles = info.get("subtitles") or info.get("automatic_captions") or {}
        for language in ("en", "en-US", "en-GB"):
            tracks = subtitles.get(language)
            if tracks:
                return f"Captions available ({len(tracks)} track(s))", True
        return None, False
