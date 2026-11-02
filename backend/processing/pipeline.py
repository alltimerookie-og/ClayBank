"""Pipeline engine orchestrating Phase 3 extraction and ASR processing (ADR 0002, ADR 0004).

Enforces non-blocking capture, atomic job claiming, deterministic stage transitions,
ephemeral media isolation, honest degraded outcomes, and safe logging.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from backend.asr.factory import get_asr_provider
from backend.asr.protocol import ASRProvider
from backend.config import settings
from backend.contracts.enums import ErrorCode, JobStage, JobState, Kind
from backend.contracts.extraction import CapabilityFlags, ExtractionResult
from backend.contracts.ids import now_iso_z
from backend.extraction.article import ArticleExtractor
from backend.extraction.captions import enrich_result_with_captions
from backend.extraction.protocol import Extractor, Tier2RescueProvider
from backend.extraction.rescue import Tier2RescueStub
from backend.extraction.ytdlp import YouTubeMetadataExtractor
from backend.processing.media import IsolatedJobMedia
from backend.store.db import Store

logger = logging.getLogger(__name__)


def is_youtube_url(url: str, platform: str) -> bool:
    """Determine whether a URL is a YouTube video."""
    if platform.lower() == "youtube":
        return True
    u = url.lower()
    return "youtube.com" in u or "youtu.be" in u


class PipelineEngine:
    """Coordinates extraction, caption retrieval, and ASR transcription for a save."""

    def __init__(
        self,
        store: Store,
        *,
        youtube_extractor: Extractor | None = None,
        article_extractor: Extractor | None = None,
        rescue_provider: Tier2RescueProvider | None = None,
        asr_provider: ASRProvider | None = None,
        media_base_dir: Path | None = None,
    ) -> None:
        self.store = store
        self.youtube_extractor = youtube_extractor or YouTubeMetadataExtractor()
        self.article_extractor = article_extractor or ArticleExtractor()
        self.rescue_provider = rescue_provider or Tier2RescueStub()
        self.asr_provider = asr_provider or get_asr_provider("local")
        self.media_base_dir = media_base_dir

        # In-memory concurrency tracking to prevent duplicate job processing
        self._active_jobs: set[str] = set()
        self._lock = asyncio.Lock()

    async def process_save(self, save_id: str, from_stage: str | None = None) -> dict[str, Any]:
        """Execute the pipeline for a save with atomic job claiming.

        Args:
            save_id: ID of the save to process.
            from_stage: Optional starting stage for reprocessing ('extracting', 'transcribing').

        Returns:
            dict[str, Any]: Summary of processing results.
        """
        # Atomic claiming: verify job is not already in-flight
        async with self._lock:
            if save_id in self._active_jobs:
                logger.info("Job %s is already active; skipping duplicate processing", save_id)
                return {"save_id": save_id, "skipped": True, "reason": "already_active"}
            self._active_jobs.add(save_id)

        try:
            return await self._execute_pipeline(save_id, from_stage)
        finally:
            async with self._lock:
                self._active_jobs.discard(save_id)

    async def _execute_pipeline(self, save_id: str, from_stage: str | None) -> dict[str, Any]:
        """Internal pipeline execution runner."""
        save = await self.store.fetchone("SELECT * FROM saves WHERE id=?", (save_id,))
        if not save:
            logger.warning("Save %s not found; aborting pipeline execution", save_id)
            return {"save_id": save_id, "error": "save_not_found"}

        job = await self.store.fetchone("SELECT * FROM jobs WHERE save_id=?", (save_id,))
        if not job:
            logger.warning("Job for save %s not found; aborting pipeline execution", save_id)
            return {"save_id": save_id, "error": "job_not_found"}

        url = save["url"]
        platform = save["platform"]

        timings: dict[str, int] = {}
        skipped: list[str] = []
        failed: list[str] = []
        last_error: str | None = None

        start_stage = (from_stage or "extracting").lower()
        extraction_res: ExtractionResult | None = None

        # ---------------------------------------------------------
        # Stage 1: EXTRACTING
        # ---------------------------------------------------------
        if start_stage == "extracting":
            t0 = time.perf_counter()
            now = now_iso_z()
            await self.store.execute(
                "UPDATE jobs SET state='extracting', error=NULL, updated_at=? WHERE save_id=?",
                (now, save_id),
            )

            try:
                extraction_res = await self._run_extraction(url, platform)
            except Exception as err:
                logger.warning("Extraction failed for save %s: %s", save_id, type(err).__name__)
                extraction_res = ExtractionResult.degraded(
                    kind=Kind.UNKNOWN,
                    source_meta={"category": "extraction_error", "status": "unavailable"},
                )
                failed.append(JobStage.EXTRACTING)
                last_error = ErrorCode.EXTRACTION_FAILED

            # Check if Tier 2 Rescue is needed
            if extraction_res.needs_tier2_rescue():
                try:
                    extraction_res = await self.rescue_provider.rescue(url, extraction_res)
                except Exception as err:
                    logger.warning("Tier 2 rescue failed for save %s: %s", save_id, type(err).__name__)

            # Persist extraction result into extraction_results table
            await self._persist_extraction_result(save_id, extraction_res)

            # Update save attributes
            await self._update_save_from_extraction(save_id, extraction_res)

            timings[JobStage.EXTRACTING] = int((time.perf_counter() - t0) * 1000)
        else:
            # Resuming from a later stage: load existing extraction result
            extraction_res = await self._load_persisted_extraction_result(save_id)
            skipped.append(JobStage.EXTRACTING)

        # ---------------------------------------------------------
        # Stage 2: TRANSCRIBING
        # ---------------------------------------------------------
        has_audio = extraction_res.capability_flags.has_audio if extraction_res else False
        transcript_available = extraction_res.transcript_available if extraction_res else False

        should_transcribe = has_audio and not transcript_available and start_stage in ("extracting", "transcribing")

        if should_transcribe:
            t0 = time.perf_counter()
            now = now_iso_z()
            await self.store.execute(
                "UPDATE jobs SET state='transcribing', updated_at=? WHERE save_id=?",
                (now, save_id),
            )

            try:
                transcript = await self._run_transcription(save_id, url)
                if transcript:
                    await self.store.execute(
                        "UPDATE notes SET transcript=?, updated_at=? WHERE save_id=?",
                        (transcript, now, save_id),
                    )
            except Exception as err:
                logger.warning("Transcription failed for save %s: %s", save_id, type(err).__name__)
                failed.append(JobStage.TRANSCRIBING)
                last_error = ErrorCode.TRANSCRIPTION_FAILED
                await self.store.execute(
                    "UPDATE saves SET needs_review=1, updated_at=? WHERE id=?",
                    (now, save_id),
                )

            timings[JobStage.TRANSCRIBING] = int((time.perf_counter() - t0) * 1000)
        else:
            skipped.append(JobStage.TRANSCRIBING)

        # ---------------------------------------------------------
        # Phase 3 Non-goals: ANALYZING & SORTING
        # ---------------------------------------------------------
        skipped.append(JobStage.ANALYZING)
        skipped.append(JobStage.SORTING)

        # ---------------------------------------------------------
        # Terminal State: READY
        # ---------------------------------------------------------
        now = now_iso_z()
        await self.store.execute(
            "UPDATE jobs SET state='ready', timing_json=?, skipped_json=?, failed_json=?,"
            " error=?, updated_at=? WHERE save_id=?",
            (
                json.dumps(timings),
                json.dumps(skipped),
                json.dumps(failed),
                last_error,
                now,
                save_id,
            ),
        )

        # Log change audit entry
        await self.store.execute(
            "INSERT INTO changes(entity, entity_id, op, at) VALUES ('job', ?, 'patch', ?)",
            (save_id, now),
        )

        return {
            "save_id": save_id,
            "state": JobState.READY,
            "timings": timings,
            "skipped": skipped,
            "failed": failed,
            "error": last_error,
        }

    async def _run_extraction(self, url: str, platform: str) -> ExtractionResult:
        """Execute tier-1 extraction based on platform and URL characteristics."""
        if is_youtube_url(url, platform):
            # 1. YouTube metadata extraction
            res = await self.youtube_extractor.extract(url, platform)
            # 2. Enrich with captions if available
            raw_meta = res.source_meta.get("raw_info")
            if isinstance(raw_meta, dict):
                res = await enrich_result_with_captions(res, raw_meta)
            return res

        # Web article extraction
        return await self.article_extractor.extract(url, platform)

    async def _run_transcription(self, save_id: str, url: str) -> str:
        """Fetch transient audio into isolated media directory and transcribe."""
        async with IsolatedJobMedia(save_id, base_dir=self.media_base_dir) as job_dir:
            audio_path = await asyncio.to_thread(self._fetch_audio_sync, url, job_dir)
            return await self.asr_provider.transcribe(audio_path)

    def _fetch_audio_sync(self, url: str, job_dir: Path) -> Path:
        """Download audio track synchronously using yt-dlp into the isolated directory."""
        import yt_dlp  # type: ignore[import-untyped]

        out_template = str(job_dir / "audio.%(ext)s")
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": out_template,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }],
            "quiet": True,
            "no_warnings": True,
            "max_filesize": 50 * 1024 * 1024,
            "socket_timeout": 15,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        wav_path = job_dir / "audio.wav"
        if wav_path.exists():
            return wav_path

        for f in job_dir.glob("*.wav"):
            return f

        raise FileNotFoundError("Audio download completed but output file was not found")

    async def _persist_extraction_result(self, save_id: str, res: ExtractionResult) -> None:
        """Persist extraction outcome to extraction_results table."""
        now = now_iso_z()
        cap_json = json.dumps(res.capability_flags.model_dump())
        meta_json = json.dumps({k: v for k, v in res.source_meta.items() if k != "raw_info"})

        await self.store.execute(
            "INSERT OR REPLACE INTO extraction_results("
            "save_id, tier, kind, title, channel, body, transcript_available, capability_json, source_meta_json, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                save_id,
                res.tier,
                res.kind.value,
                res.title,
                res.channel,
                res.body,
                1 if res.transcript_available else 0,
                cap_json,
                meta_json,
                now,
            ),
        )

    async def _update_save_from_extraction(self, save_id: str, res: ExtractionResult) -> None:
        """Update saves and notes rows with extracted facts."""
        now = now_iso_z()
        await self.store.execute(
            "UPDATE saves SET "
            "title = COALESCE(?, title), "
            "kind = ?, "
            "has_audio = ?, "
            "has_timeline = ?, "
            "has_images = ?, "
            "duration = COALESCE(?, duration), "
            "updated_at = ? "
            "WHERE id = ?",
            (
                res.title,
                res.kind.value,
                1 if res.capability_flags.has_audio else 0,
                1 if res.capability_flags.has_timeline else 0,
                1 if res.capability_flags.has_images else 0,
                res.duration,
                now,
                save_id,
            ),
        )

        # Update note metadata
        if res.transcript_available and res.body:
            await self.store.execute(
                "UPDATE notes SET "
                "channel = COALESCE(?, channel), "
                "duration = COALESCE(?, duration), "
                "published = COALESCE(?, published), "
                "transcript = ?, "
                "updated_at = ? "
                "WHERE save_id = ?",
                (res.channel, res.duration, res.published, res.body, now, save_id),
            )
        else:
            await self.store.execute(
                "UPDATE notes SET "
                "channel = COALESCE(?, channel), "
                "duration = COALESCE(?, duration), "
                "published = COALESCE(?, published), "
                "updated_at = ? "
                "WHERE save_id = ?",
                (res.channel, res.duration, res.published, now, save_id),
            )

    async def _load_persisted_extraction_result(self, save_id: str) -> ExtractionResult:
        """Load previously stored extraction result for reprocessing."""
        row = await self.store.fetchone("SELECT * FROM extraction_results WHERE save_id=?", (save_id,))
        if not row:
            return ExtractionResult.empty()

        caps = CapabilityFlags()
        try:
            if row.get("capability_json"):
                caps = CapabilityFlags.model_validate(json.loads(row["capability_json"]))
        except Exception:
            pass

        meta: dict[str, Any] = {}
        try:
            if row.get("source_meta_json"):
                meta = json.loads(row["source_meta_json"])
        except Exception:
            pass

        return ExtractionResult(
            tier=row["tier"],
            kind=Kind(row["kind"]),
            title=row.get("title"),
            channel=row.get("channel"),
            duration=None,
            published=None,
            body=row.get("body"),
            transcript_available=bool(row.get("transcript_available", 0)),
            capability_flags=caps,
            source_meta=meta,
        )
