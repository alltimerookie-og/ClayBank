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
from backend.llm.meta import MetaLLMProvider
from backend.llm.protocol import LLMProvider
from backend.processing.media import IsolatedJobMedia
from backend.processing.notes import (
    build_frontmatter_yaml,
    execute_note_persistence_transaction,
    generate_note_markdown,
    parse_frontmatter,
)
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
        llm_provider: LLMProvider | None = None,
        media_base_dir: Path | None = None,
    ) -> None:
        self.store = store
        self.youtube_extractor = youtube_extractor or YouTubeMetadataExtractor()
        self.article_extractor = article_extractor or ArticleExtractor()
        self.rescue_provider = rescue_provider or Tier2RescueStub()
        self.asr_provider = asr_provider or get_asr_provider("local")
        self.llm_provider = llm_provider or MetaLLMProvider()
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
        except asyncio.CancelledError:
            logger.warning(
                "Pipeline execution cancelled for save %s; resetting job state to queued", save_id
            )
            now = now_iso_z()
            try:
                await self.store.execute(
                    "UPDATE jobs SET state='queued', error=NULL, updated_at=? WHERE save_id=?",
                    (now, save_id),
                )
            except Exception as db_err:
                logger.debug("Could not reset job %s to queued on cancellation: %s", save_id, db_err)
            raise
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
        transcript_text: str | None = extraction_res.body if (extraction_res and extraction_res.transcript_available) else None

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
                    transcript_text = transcript
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
        # Stage 3: ANALYZING
        # ---------------------------------------------------------
        should_analyze = start_stage in ("extracting", "transcribing", "analyzing")

        if should_analyze:
            t0 = time.perf_counter()
            now = now_iso_z()
            await self.store.execute(
                "UPDATE jobs SET state='analyzing', updated_at=? WHERE save_id=?",
                (now, save_id),
            )

            existing_note = await self.store.fetchone("SELECT * FROM notes WHERE save_id=?", (save_id,))
            has_existing_body = False
            if existing_note and existing_note.get("markdown"):
                _, existing_body = parse_frontmatter(existing_note["markdown"])
                if existing_body.strip() and existing_note.get("overview"):
                    has_existing_body = True

            # Invariant (ADR 0005): Reprocessing from extracting/transcribing never modifies note body.
            # Only explicit 'from=analyzing' regenerates the body text.
            if has_existing_body and start_stage in ("extracting", "transcribing"):
                # Reprocess re-run: update stable frontmatter facts only, keep user body untouched
                assert existing_note is not None
                facts = {
                    "source": platform,
                    "channel": save.get("channel") or (extraction_res.channel if extraction_res else None),
                    "video_url": save.get("url") if is_youtube_url(url, platform) else None,
                    "duration": save.get("duration") or (extraction_res.duration if extraction_res else None),
                    "published": extraction_res.published if extraction_res else None,
                    "saved": save.get("captured_at", now)[:10] if save.get("captured_at") else None,
                    "folder": existing_note.get("folder_path"),
                    "tags": json.loads(existing_note["tags_json"]) if existing_note.get("tags_json") else [],
                }
                _, body_only = parse_frontmatter(existing_note["markdown"])
                updated_md = build_frontmatter_yaml(facts) + body_only

                rerun_overview = existing_note.get("overview")
                rerun_kp = json.loads(existing_note["key_points_json"]) if existing_note.get("key_points_json") else None
                rerun_links = json.loads(existing_note["links_json"]) if existing_note.get("links_json") else None
                rerun_transcript = existing_note.get("transcript")

                def _tx_rerun(conn: Any) -> None:
                    execute_note_persistence_transaction(
                        conn=conn,
                        save_id=save_id,
                        markdown=updated_md,
                        overview=rerun_overview,
                        key_points=rerun_kp,
                        links=rerun_links,
                        transcript=rerun_transcript,
                        now=now,
                    )
                await self.store.run_tx(_tx_rerun)
            else:
                # Initial note generation or explicit 'from=analyzing'
                if not transcript_text:
                    transcript_text = (existing_note.get("transcript") if existing_note else None) or (
                        extraction_res.body if (extraction_res and extraction_res.transcript_available) else None
                    )

                article_body = extraction_res.body if (extraction_res and not extraction_res.transcript_available) else None
                if not article_body and save.get("user_context"):
                    article_body = save.get("user_context")

                content_to_analyze = transcript_text or article_body or ""
                save_title = save.get("title") or (extraction_res.title if extraction_res else None) or "Untitled Save"
                save_channel = (extraction_res.channel if extraction_res else None) or save.get("channel")
                save_kind = save.get("kind") or (extraction_res.kind.value if extraction_res else "unknown")

                facts = {
                    "source": platform,
                    "channel": save_channel,
                    "video_url": save.get("url") if is_youtube_url(url, platform) else None,
                    "duration": save.get("duration") or (extraction_res.duration if extraction_res else None),
                    "published": extraction_res.published if extraction_res else None,
                    "saved": save.get("captured_at", now)[:10] if save.get("captured_at") else None,
                    "folder": existing_note.get("folder_path") if existing_note else None,
                    "tags": json.loads(existing_note["tags_json"]) if (existing_note and existing_note.get("tags_json")) else [],
                }

                if content_to_analyze.strip():
                    try:
                        llm_res = await self.llm_provider.generate_note(
                            title=save_title,
                            kind=save_kind,
                            content=content_to_analyze,
                            user_context=save.get("user_context"),
                        )
                    except Exception as llm_err:
                        logger.warning("Unhandled LLM exception for save %s: %s", save_id, type(llm_err).__name__)
                        from backend.llm.models import NoteGenerationResult
                        llm_res = NoteGenerationResult(
                            is_success=False,
                            error_category="generation_error",
                        )

                    if llm_res.is_success and llm_res.structured_output:
                        structured = llm_res.structured_output
                        note_md = generate_note_markdown(
                            title=save_title,
                            facts=facts,
                            structured=structured,
                            transcript=transcript_text,
                        )

                        links_dicts = [l.model_dump() for l in structured.links]

                        def _tx_success(conn: Any) -> None:
                            execute_note_persistence_transaction(
                                conn=conn,
                                save_id=save_id,
                                markdown=note_md,
                                overview=structured.overview,
                                key_points=structured.key_points,
                                links=links_dicts,
                                transcript=transcript_text,
                                now=now,
                            )
                        await self.store.run_tx(_tx_success)
                    else:
                        # Controlled graceful degradation
                        logger.warning(
                            "LLM note generation degraded for save %s: %s",
                            save_id,
                            llm_res.error_category or "unknown_error",
                        )
                        failed.append(JobStage.ANALYZING)
                        if last_error is None:
                            last_error = ErrorCode.LLM_UNAVAILABLE

                        degraded_md = generate_note_markdown(
                            title=save_title,
                            facts=facts,
                            structured=None,
                            transcript=transcript_text,
                            raw_body=article_body,
                        )

                        def _tx_fail(conn: Any) -> None:
                            execute_note_persistence_transaction(
                                conn=conn,
                                save_id=save_id,
                                markdown=degraded_md,
                                overview=None,
                                key_points=None,
                                links=None,
                                transcript=transcript_text,
                                now=now,
                            )
                            conn.execute(
                                "UPDATE saves SET needs_review=1, updated_at=? WHERE id=?",
                                (now, save_id),
                            )
                        await self.store.run_tx(_tx_fail)
                else:
                    logger.info("No content to analyze for save %s; synthesizing degraded shell", save_id)
                    failed.append(JobStage.ANALYZING)
                    if last_error is None:
                        last_error = ErrorCode.EXTRACTION_FAILED

                    degraded_md = generate_note_markdown(
                        title=save_title,
                        facts=facts,
                        structured=None,
                        transcript=None,
                        raw_body=None,
                    )

                    def _tx_nocontent(conn: Any) -> None:
                        execute_note_persistence_transaction(
                            conn=conn,
                            save_id=save_id,
                            markdown=degraded_md,
                            overview=None,
                            key_points=None,
                            links=None,
                            transcript=None,
                            now=now,
                        )
                        conn.execute(
                            "UPDATE saves SET needs_review=1, updated_at=? WHERE id=?",
                            (now, save_id),
                        )
                    await self.store.run_tx(_tx_nocontent)

            timings[JobStage.ANALYZING] = int((time.perf_counter() - t0) * 1000)
        else:
            skipped.append(JobStage.ANALYZING)

        # ---------------------------------------------------------
        # Phase 4 Non-goals: SORTING (deferred to Phase 6)
        # ---------------------------------------------------------
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
            loop = asyncio.get_running_loop()
            fetch_fut = loop.run_in_executor(None, self._fetch_audio_sync, url, job_dir)
            try:
                audio_path = await asyncio.shield(fetch_fut)
            except asyncio.CancelledError:
                while not fetch_fut.done():
                    try:
                        await asyncio.shield(fetch_fut)
                    except asyncio.CancelledError:
                        pass
                    except Exception:
                        break
                if fetch_fut.done() and not fetch_fut.cancelled():
                    _ = fetch_fut.exception()
                raise

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
