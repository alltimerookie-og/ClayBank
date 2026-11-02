"""Tests for Phase 3 Task 5: Pipeline Engine, Reprocessing, and Recovery (ADR 0002, ADR 0004).

Verifies end-to-end pipeline orchestration, state transitions, atomic job claiming,
failure degradation, startup recovery, and reprocessing from requested stages.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch
import pytest

from backend.contracts.enums import ErrorCode, JobStage, JobState, Kind
from backend.contracts.extraction import CapabilityFlags, ExtractionResult
from backend.contracts.ids import new_uuid7, now_iso_z
from backend.processing.pipeline import PipelineEngine
from backend.processing.recovery import recover_stale_jobs
from backend.store.db import Store


# --- Mock Providers ---

class MockExtractor:
    def __init__(self, result: ExtractionResult | None = None, raise_err: Exception | None = None) -> None:
        self.result = result or ExtractionResult(
            tier=1,
            kind=Kind.ARTICLE,
            title="Pipeline Article Title",
            channel="Jane Journalist",
            body="A substantive article body for pipeline testing.",
            transcript_available=False,
            capability_flags=CapabilityFlags(has_audio=False, has_timeline=False, has_images=False),
        )
        self.raise_err = raise_err
        self.calls: list[tuple[str, str]] = []

    async def extract(self, url: str, platform: str) -> ExtractionResult:
        self.calls.append((url, platform))
        if self.raise_err:
            raise self.raise_err
        return self.result


class MockASRProvider:
    def __init__(self, transcript: str = "Transcribed speech text from audio.", raise_err: Exception | None = None) -> None:
        self.transcript = transcript
        self.raise_err = raise_err
        self.transcribe_calls: list[Path] = []

    async def transcribe(self, audio_path: Path, language: str | None = None) -> str:
        self.transcribe_calls.append(audio_path)
        if self.raise_err:
            raise self.raise_err
        return self.transcript


class MockLLMProvider:
    def __init__(self, raise_err: Exception | None = None) -> None:
        self.raise_err = raise_err

    async def generate_note(self, title: str, kind: str, content: str, user_context: str | None = None):
        if self.raise_err:
            raise self.raise_err
        from backend.llm.models import NoteGenerationResult, NoteStructuredOutput
        return NoteGenerationResult(
            is_success=True,
            structured_output=NoteStructuredOutput(
                overview=f"Overview of {title}",
                key_points=["Key point 1", "Key point 2"],
                links=[],
            ),
        )


@pytest.fixture(autouse=True)
def default_mock_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.processing import pipeline
    original_init = pipeline.PipelineEngine.__init__

    def _init_with_mock_llm(self: Any, *args: Any, **kwargs: Any) -> None:
        if "llm_provider" not in kwargs or kwargs["llm_provider"] is None:
            kwargs["llm_provider"] = MockLLMProvider()
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(pipeline.PipelineEngine, "__init__", _init_with_mock_llm)


async def seed_test_save(store: Store, url: str = "https://example.com/article", platform: str = "web") -> str:
    """Helper to insert a test save and initial queued job."""
    save_id = new_uuid7()
    now = now_iso_z()

    def _tx(conn):
        conn.execute(
            "INSERT INTO saves(id, raw_url, url, platform, source_app, user_context, captured_at, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 'test', '', ?, ?, ?)",
            (save_id, url, url, platform, now, now, now),
        )
        conn.execute(
            "INSERT INTO notes(save_id, markdown, created_at, updated_at) VALUES (?, '---\n---\n', ?, ?)",
            (save_id, now, now),
        )
        conn.execute(
            "INSERT INTO jobs(save_id, state, tier, created_at, updated_at) VALUES (?, 'queued', 1, ?, ?)",
            (save_id, now, now),
        )

    await store.run_tx(_tx)
    return save_id


# --- Pipeline Engine Tests ---

@pytest.mark.anyio
async def test_pipeline_normal_article_extraction(tmp_path: Path) -> None:
    """Verify normal article pipeline execution completes at ready without ASR."""
    db_path = tmp_path / "test.db"
    store = Store(str(db_path))
    save_id = await seed_test_save(store, "https://example.com/story", platform="web")

    extractor = MockExtractor()
    asr = MockASRProvider()
    engine = PipelineEngine(store, article_extractor=extractor, asr_provider=asr, media_base_dir=tmp_path / "media")

    res = await engine.process_save(save_id)

    assert res["state"] == JobState.READY
    assert res["failed"] == []
    assert JobStage.TRANSCRIBING in res["skipped"]

    job = await store.fetchone("SELECT * FROM jobs WHERE save_id=?", (save_id,))
    assert job is not None
    assert job["state"] == "ready"
    assert job["error"] is None

    save = await store.fetchone("SELECT * FROM saves WHERE id=?", (save_id,))
    assert save is not None
    assert save["title"] == "Pipeline Article Title"
    assert save["kind"] == "article"
    assert save["has_audio"] == 0


@pytest.mark.anyio
async def test_pipeline_video_with_captions_skips_asr(tmp_path: Path) -> None:
    """Verify video with caption transcript available skips the transcribing stage."""
    db_path = tmp_path / "test.db"
    store = Store(str(db_path))
    save_id = await seed_test_save(store, "https://youtube.com/watch?v=captions1", platform="youtube")

    video_result = ExtractionResult(
        tier=1,
        kind=Kind.VIDEO,
        title="Video With Captions",
        channel="Video Creator",
        duration=120,
        body="Transcript text directly extracted from captions track.",
        transcript_available=True,
        capability_flags=CapabilityFlags(has_audio=True, has_timeline=False, has_images=False),
    )
    yt_extractor = MockExtractor(result=video_result)
    asr = MockASRProvider()

    engine = PipelineEngine(
        store,
        youtube_extractor=yt_extractor,
        asr_provider=asr,
        media_base_dir=tmp_path / "media",
    )

    res = await engine.process_save(save_id)

    assert res["state"] == JobState.READY
    assert len(asr.transcribe_calls) == 0  # ASR was skipped!
    assert JobStage.TRANSCRIBING in res["skipped"]

    note = await store.fetchone("SELECT * FROM notes WHERE save_id=?", (save_id,))
    assert note is not None
    assert note["transcript"] == "Transcript text directly extracted from captions track."


@pytest.mark.anyio
async def test_pipeline_video_without_captions_invokes_asr(tmp_path: Path) -> None:
    """Verify video without captions runs transcribing stage and updates note transcript."""
    db_path = tmp_path / "test.db"
    store = Store(str(db_path))
    save_id = await seed_test_save(store, "https://youtube.com/watch?v=no_captions", platform="youtube")

    video_result = ExtractionResult(
        tier=1,
        kind=Kind.VIDEO,
        title="Spoken Video Without Captions",
        channel="Speaker",
        duration=60,
        body=None,
        transcript_available=False,
        capability_flags=CapabilityFlags(has_audio=True, has_timeline=False, has_images=False),
    )
    yt_extractor = MockExtractor(result=video_result)
    asr = MockASRProvider(transcript="Full speech transcript generated by faster-whisper.")

    engine = PipelineEngine(
        store,
        youtube_extractor=yt_extractor,
        asr_provider=asr,
        media_base_dir=tmp_path / "media",
    )

    # Mock audio fetching to provide a fake audio file in the isolated directory
    def fake_fetch_audio(url: str, job_dir: Path) -> Path:
        audio = job_dir / "audio.wav"
        audio.write_bytes(b"RIFF_FAKE_AUDIO_DATA")
        return audio

    with patch.object(engine, "_fetch_audio_sync", side_effect=fake_fetch_audio):
        res = await engine.process_save(save_id)

    assert res["state"] == JobState.READY
    assert len(asr.transcribe_calls) == 1
    assert res["failed"] == []

    note = await store.fetchone("SELECT * FROM notes WHERE save_id=?", (save_id,))
    assert note is not None
    assert note["transcript"] == "Full speech transcript generated by faster-whisper."


@pytest.mark.anyio
async def test_pipeline_extraction_failure_degrades_gracefully(tmp_path: Path) -> None:
    """Verify extraction failure records error and finishes at ready with needs_review=1."""
    db_path = tmp_path / "test.db"
    store = Store(str(db_path))
    save_id = await seed_test_save(store, "https://example.com/broken", platform="web")

    extractor = MockExtractor(raise_err=RuntimeError("Extraction connection died"))
    engine = PipelineEngine(store, article_extractor=extractor, media_base_dir=tmp_path / "media")

    res = await engine.process_save(save_id)

    assert res["state"] == JobState.READY
    assert JobStage.EXTRACTING in res["failed"]

    job = await store.fetchone("SELECT * FROM jobs WHERE save_id=?", (save_id,))
    assert job is not None
    assert job["state"] == "ready"
    assert job["error"] == ErrorCode.EXTRACTION_FAILED


@pytest.mark.anyio
async def test_pipeline_transcription_failure_degrades_gracefully(tmp_path: Path) -> None:
    """Verify transcription failure records error and completes at ready."""
    db_path = tmp_path / "test.db"
    store = Store(str(db_path))
    save_id = await seed_test_save(store, "https://youtube.com/watch?v=asr_fail", platform="youtube")

    video_result = ExtractionResult(
        tier=1,
        kind=Kind.VIDEO,
        title="Video Failing ASR",
        capability_flags=CapabilityFlags(has_audio=True, has_timeline=False, has_images=False),
        transcript_available=False,
    )
    yt_extractor = MockExtractor(result=video_result)
    asr = MockASRProvider(raise_err=RuntimeError("Model crashed"))

    engine = PipelineEngine(
        store,
        youtube_extractor=yt_extractor,
        asr_provider=asr,
        media_base_dir=tmp_path / "media",
    )

    def fake_fetch_audio(url: str, job_dir: Path) -> Path:
        audio = job_dir / "audio.wav"
        audio.write_bytes(b"RIFF_FAKE_AUDIO_DATA")
        return audio

    with patch.object(engine, "_fetch_audio_sync", side_effect=fake_fetch_audio):
        res = await engine.process_save(save_id)

    assert res["state"] == JobState.READY
    assert JobStage.TRANSCRIBING in res["failed"]

    job = await store.fetchone("SELECT * FROM jobs WHERE save_id=?", (save_id,))
    assert job is not None
    assert job["state"] == "ready"
    assert job["error"] == ErrorCode.TRANSCRIPTION_FAILED

    save = await store.fetchone("SELECT * FROM saves WHERE id=?", (save_id,))
    assert save is not None
    assert save["needs_review"] == 1


@pytest.mark.anyio
async def test_atomic_job_claiming_prevents_duplicate_execution(tmp_path: Path) -> None:
    """Verify concurrent requests for the same save_id skip duplicate processing."""
    db_path = tmp_path / "test.db"
    store = Store(str(db_path))
    save_id = await seed_test_save(store, "https://example.com/concurrent", platform="web")

    class SlowExtractor:
        async def extract(self, url: str, platform: str) -> ExtractionResult:
            await asyncio.sleep(0.1)
            return ExtractionResult.empty()

    engine = PipelineEngine(store, article_extractor=SlowExtractor(), media_base_dir=tmp_path / "media")

    task1 = asyncio.create_task(engine.process_save(save_id))
    await asyncio.sleep(0.01)  # Allow task1 to claim save_id
    task2 = asyncio.create_task(engine.process_save(save_id))

    res1, res2 = await asyncio.gather(task1, task2)

    assert res1.get("state") == JobState.READY
    assert res2.get("skipped") is True
    assert res2.get("reason") == "already_active"


# --- Recovery Tests ---

@pytest.mark.anyio
async def test_startup_recovery_resets_interrupted_jobs(tmp_path: Path) -> None:
    """Verify recover_stale_jobs resets jobs left in extracting/transcribing to queued."""
    db_path = tmp_path / "test.db"
    store = Store(str(db_path))

    save1 = await seed_test_save(store, "https://example.com/stale1")
    save2 = await seed_test_save(store, "https://example.com/stale2")
    save3 = await seed_test_save(store, "https://example.com/done")

    now = now_iso_z()
    await store.execute("UPDATE jobs SET state='extracting', updated_at=? WHERE save_id=?", (now, save1))
    await store.execute("UPDATE jobs SET state='transcribing', updated_at=? WHERE save_id=?", (now, save2))
    await store.execute("UPDATE jobs SET state='ready', updated_at=? WHERE save_id=?", (now, save3))

    recovered = await recover_stale_jobs(store, pipeline=None)
    assert recovered == 2

    job1 = await store.fetchone("SELECT * FROM jobs WHERE save_id=?", (save1,))
    job2 = await store.fetchone("SELECT * FROM jobs WHERE save_id=?", (save2,))
    job3 = await store.fetchone("SELECT * FROM jobs WHERE save_id=?", (save3,))

    assert job1 is not None
    assert job2 is not None
    assert job3 is not None
    assert job1["state"] == "queued"
    assert job2["state"] == "queued"
    assert job3["state"] == "ready"  # Completed job was untouched!


# --- Reprocess API Tests ---

@pytest.mark.anyio
async def test_reprocess_endpoint_requeues_job(tmp_path: Path) -> None:
    """Verify POST /saves/{save_id}/reprocess sets state to queued and returns 202."""
    from httpx import ASGITransport, AsyncClient
    from backend.main import create_app

    db_path = tmp_path / "test.db"
    store = Store(str(db_path))
    save_id = await seed_test_save(store, "https://example.com/reprocess-test")

    now = now_iso_z()
    await store.execute("UPDATE jobs SET state='ready', error='some_err', updated_at=? WHERE save_id=?", (now, save_id))

    app = create_app(store, media_base_dir=tmp_path / "media")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/saves/{save_id}/reprocess?from=transcribing",
            headers={"Authorization": "Bearer dev-token-change-me", "X-Device-Id": "test-device"},
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["data"]["state"] == "queued"
        assert body["data"]["from"] == "transcribing"

    job = await store.fetchone("SELECT * FROM jobs WHERE save_id=?", (save_id,))
    assert job is not None
    assert job["state"] == "queued"
    assert job["error"] is None


# --- Remediation Tests: CB-P3-006 (Pipeline Cancellation State) ---

@pytest.mark.anyio
async def test_pipeline_cancellation_during_extraction_resets_state_to_queued(tmp_path: Path) -> None:
    """Verify cancellation during extraction resets jobs.state to queued and frees active job lock (CB-P3-006)."""
    db_path = tmp_path / "test.db"
    store = Store(str(db_path))
    save_id = await seed_test_save(store, "https://example.com/slow-extract")

    class SlowExtractor:
        async def extract(self, url: str, platform: str) -> ExtractionResult:
            await asyncio.sleep(0.5)
            return ExtractionResult.empty()

    engine = PipelineEngine(
        store,
        article_extractor=SlowExtractor(),
        media_base_dir=tmp_path / "media",
    )

    task = asyncio.create_task(engine.process_save(save_id))
    # Await transition into extracting state
    job_before = None
    for _ in range(50):
        await asyncio.sleep(0.02)
        job_before = await store.fetchone("SELECT state FROM jobs WHERE save_id=?", (save_id,))
        if job_before and job_before["state"] == "extracting":
            break

    # Job is active in engine
    assert save_id in engine._active_jobs
    assert job_before is not None
    assert job_before["state"] == "extracting"

    # Cancel task
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    # Assert active-job tracking is cleared
    assert save_id not in engine._active_jobs

    # Assert DB state was reset to queued (not left in extracting!)
    job_after = await store.fetchone("SELECT state, error FROM jobs WHERE save_id=?", (save_id,))
    assert job_after is not None
    assert job_after["state"] == "queued"
    assert job_after["error"] is None

    # Assert subsequent reprocessing succeeds immediately without duplicate-active rejection
    quick_extractor = MockExtractor()
    engine.article_extractor = quick_extractor
    res_reprocess = await engine.process_save(save_id)
    assert res_reprocess["state"] == JobState.READY
    job_final = await store.fetchone("SELECT state FROM jobs WHERE save_id=?", (save_id,))
    assert job_final is not None
    assert job_final["state"] == "ready"


@pytest.mark.anyio
async def test_pipeline_cancellation_during_transcription_resets_state_and_cleans_media(tmp_path: Path) -> None:
    """Verify cancellation during ASR resets state to queued and cleans temporary media (CB-P3-006)."""
    db_path = tmp_path / "test.db"
    store = Store(str(db_path))
    save_id = await seed_test_save(store, "https://youtube.com/watch?v=slow_asr")

    video_result = ExtractionResult(
        tier=1,
        kind=Kind.VIDEO,
        title="Video Slow ASR",
        capability_flags=CapabilityFlags(has_audio=True, has_timeline=False, has_images=False),
        transcript_available=False,
    )
    yt_extractor = MockExtractor(result=video_result)

    class SlowASR:
        async def transcribe(self, audio_path: Path, language: str | None = None) -> str:
            await asyncio.sleep(0.5)
            return "Transcript"

    media_dir = tmp_path / "media"
    engine = PipelineEngine(
        store,
        youtube_extractor=yt_extractor,
        asr_provider=SlowASR(),
        media_base_dir=media_dir,
    )

    def fake_fetch_audio(url: str, job_dir: Path) -> Path:
        audio = job_dir / "audio.wav"
        audio.write_bytes(b"RIFF_FAKE_AUDIO_DATA")
        return audio

    # Seed existing extraction result with has_audio=True
    await engine._persist_extraction_result(save_id, video_result)
    await engine._update_save_from_extraction(save_id, video_result)

    with patch.object(engine, "_fetch_audio_sync", side_effect=fake_fetch_audio):
        task = asyncio.create_task(engine.process_save(save_id, from_stage="transcribing"))
        # Await transition into transcribing state
        job_in_flight = None
        for _ in range(50):
            await asyncio.sleep(0.02)
            job_in_flight = await store.fetchone("SELECT state FROM jobs WHERE save_id=?", (save_id,))
            if job_in_flight and job_in_flight["state"] == "transcribing":
                break

        assert save_id in engine._active_jobs
        assert job_in_flight is not None
        assert job_in_flight["state"] == "transcribing"

        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    # Assert active-job tracking is cleared
    assert save_id not in engine._active_jobs

    # Assert DB state reset to queued
    job_cancelled = await store.fetchone("SELECT state, error FROM jobs WHERE save_id=?", (save_id,))
    assert job_cancelled is not None
    assert job_cancelled["state"] == "queued"
    assert job_cancelled["error"] is None

    # Assert temporary media cleaned up
    remaining_job_dirs = list(media_dir.glob("job_*"))
    assert len(remaining_job_dirs) == 0
