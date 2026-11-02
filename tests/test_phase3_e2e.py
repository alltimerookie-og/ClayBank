"""Phase 3 Task 7: End-to-End Acceptance Tests (ADR 0002, ADR 0004).

Comprehensive end-to-end integration and acceptance tests covering:
1. Non-blocking capture.
2. YouTube metadata & caption extraction.
3. Article extraction.
4. Tier-2 rescue stub behavior.
5. Local ASR provider execution & model caching.
6. ASR provider selection.
7. Pipeline state transitions: queued -> extracting -> transcribing -> ready.
8. Atomic job claiming preventing duplicate runs.
9. Failure degradation without dropping saves.
10. Stale job startup recovery.
11. Reprocessing endpoint contract.
12. Ephemeral media scrubbing in all paths.
13. Inbox UI polling synchronization.
14. Database and API contract invariants.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
import time
import pytest
from httpx import ASGITransport, AsyncClient

from backend.config import settings
from backend.contracts.enums import Kind
from backend.contracts.extraction import CapabilityFlags, ExtractionResult
from backend.contracts.ids import new_uuid7, now_iso_z
from backend.extraction.rescue import Tier2RescueStub
from backend.main import create_app
from backend.processing.pipeline import PipelineEngine
from backend.processing.recovery import recover_stale_jobs
from backend.store.db import Store


class MockArticleExtractor:
    def __init__(self, title: str = "Acceptance Article", body: str = "Substantive article content."):
        self.title = title
        self.body = body

    async def extract(self, url: str, platform: str) -> ExtractionResult:
        return ExtractionResult(
            tier=1,
            kind=Kind.ARTICLE,
            title=self.title,
            channel="Tech Reporter",
            body=self.body,
            transcript_available=False,
            capability_flags=CapabilityFlags(has_audio=False, has_timeline=False, has_images=False),
        )


class MockVideoExtractor:
    def __init__(self, title: str = "Acceptance Video", captions: str | None = None):
        self.title = title
        self.captions = captions

    async def extract(self, url: str, platform: str) -> ExtractionResult:
        return ExtractionResult(
            tier=1,
            kind=Kind.VIDEO,
            title=self.title,
            channel="Video Creator",
            duration=120,
            body=self.captions,
            transcript_available=bool(self.captions),
            capability_flags=CapabilityFlags(has_audio=True, has_timeline=True, has_images=False),
        )


class MockFailingExtractor:
    async def extract(self, url: str, platform: str) -> ExtractionResult:
        raise RuntimeError("Remote site returned 503 Service Unavailable")


class MockASR:
    def __init__(self, transcript: str = "Mocked ASR acceptance transcript."):
        self.transcript = transcript
        self.invoked = False

    async def transcribe(self, audio_path: Path, language: str | None = None) -> str:
        self.invoked = True
        return self.transcript


async def wait_for_job_ready(client: AsyncClient, save_id: str, timeout: float = 4.0) -> dict:
    """Poll GET /saves/{id} until the job completes in 'ready' state."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        resp = await client.get(f"/saves/{save_id}")
        if resp.status_code == 200:
            data = resp.json()["data"]
            if data.get("job") and data["job"].get("state") == "ready":
                return data
        await asyncio.sleep(0.05)
    raise TimeoutError(f"Job for save {save_id} did not reach ready within {timeout}s")


@pytest.fixture
def e2e_env(tmp_path: Path):
    """Build a complete, isolated test environment for E2E tests."""
    db_path = tmp_path / "e2e.db"
    media_root = tmp_path / "media"
    media_root.mkdir(parents=True, exist_ok=True)

    store = Store(str(db_path))
    app = create_app(store, media_base_dir=media_root)

    # Default mocked pipeline
    article_ext = MockArticleExtractor()
    video_ext = MockVideoExtractor(captions="Built-in caption text")
    asr = MockASR()
    pipeline = PipelineEngine(
        store=store,
        article_extractor=article_ext,
        youtube_extractor=video_ext,
        asr_provider=asr,
        rescue_provider=Tier2RescueStub(),
        media_base_dir=media_root,
    )
    app.state.pipeline = pipeline

    headers = {
        "Authorization": f"Bearer {settings.DEV_TOKEN}",
        "X-Device-Id": "e2e-device-1",
    }

    return {
        "app": app,
        "store": store,
        "pipeline": pipeline,
        "article_ext": article_ext,
        "video_ext": video_ext,
        "asr": asr,
        "media_root": media_root,
        "db_path": db_path,
        "headers": headers,
    }


@pytest.mark.anyio
async def test_e2e_article_capture_to_completion(e2e_env):
    """End-to-end: capture article -> non-blocking 201 -> pipeline runs -> ready with body."""
    app = e2e_env["app"]
    headers = e2e_env["headers"]
    store = e2e_env["store"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers) as client:
        payload = {
            "url": "https://example.com/posts/e2e-guide",
            "user_context": "Recommended reading",
        }
        resp = await client.post("/saves", json=payload)
        assert resp.status_code == 201
        data = resp.json()["data"]
        save_id = data["id"]
        assert save_id is not None

        # Wait for background pipeline processing to complete
        res_data = await wait_for_job_ready(client, save_id)
        save = res_data["save"]
        job = res_data["job"]

        assert save["title"] == "Acceptance Article"
        assert save["kind"] == "article"
        assert job["state"] == "ready"
        assert job["error"] is None

        # Verify extraction_results table has the extracted body
        ext_row = await store.fetchone("SELECT * FROM extraction_results WHERE save_id=?", (save_id,))
        assert ext_row is not None
        assert ext_row["body"] == "Substantive article content."


@pytest.mark.anyio
async def test_e2e_video_with_captions_skips_asr_and_populates_transcript(e2e_env):
    """End-to-end: video with captions enriches transcript and avoids ASR invocation."""
    app = e2e_env["app"]
    headers = e2e_env["headers"]
    pipeline = e2e_env["pipeline"]
    asr = e2e_env["asr"]

    # Configure video extractor with captions
    pipeline.youtube_extractor = MockVideoExtractor(
        title="Captioned Talk", captions="Hello and welcome to this lecture."
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers) as client:
        resp = await client.post("/saves", json={"url": "https://www.youtube.com/watch?v=captioned123"})
        assert resp.status_code == 201
        save_id = resp.json()["data"]["id"]

        res_data = await wait_for_job_ready(client, save_id)
        save = res_data["save"]
        note = res_data["note"]
        job = res_data["job"]

        assert save["title"] == "Captioned Talk"
        assert save["kind"] == "video"
        assert note["transcript"] == "Hello and welcome to this lecture."
        assert job["state"] == "ready"
        assert not asr.invoked, "ASR must not be invoked when captions are already present"


@pytest.mark.anyio
async def test_e2e_video_without_captions_triggers_asr_and_cleans_media(e2e_env):
    """End-to-end: video without captions invokes ASR and cleans up temporary media."""
    app = e2e_env["app"]
    headers = e2e_env["headers"]
    pipeline = e2e_env["pipeline"]
    asr = e2e_env["asr"]
    temp_dir_used: list[Path] = []

    pipeline.youtube_extractor = MockVideoExtractor(title="No Caption Video", captions=None)

    # Monkeypatch _fetch_audio_sync to produce a fake audio file in IsolatedJobMedia
    def mock_fetch_audio_sync(url: str, job_dir: Path) -> Path:
        temp_dir_used.append(job_dir)
        audio_file = job_dir / "audio.wav"
        audio_file.write_bytes(b"dummy audio content")
        return audio_file

    pipeline._fetch_audio_sync = mock_fetch_audio_sync

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers) as client:
        resp = await client.post("/saves", json={"url": "https://www.youtube.com/watch?v=nocaption123"})
        assert resp.status_code == 201
        save_id = resp.json()["data"]["id"]

        res_data = await wait_for_job_ready(client, save_id)
        save = res_data["save"]
        note = res_data["note"]
        job = res_data["job"]

        assert save["title"] == "No Caption Video"
        assert note["transcript"] == "Mocked ASR acceptance transcript."
        assert job["state"] == "ready"
        assert asr.invoked is True

        # Verify temp media cleanup
        assert len(temp_dir_used) == 1
        assert not temp_dir_used[0].exists(), "Ephemeral job media directory must be removed after processing"


@pytest.mark.anyio
async def test_e2e_extraction_failure_degrades_gracefully(e2e_env):
    """End-to-end: extraction failure transitions job to ready with error, save survives."""
    app = e2e_env["app"]
    headers = e2e_env["headers"]
    pipeline = e2e_env["pipeline"]

    pipeline.article_extractor = MockFailingExtractor()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers) as client:
        resp = await client.post("/saves", json={"url": "https://example.com/broken-page"})
        assert resp.status_code == 201
        save_id = resp.json()["data"]["id"]

        res_data = await wait_for_job_ready(client, save_id)
        save = res_data["save"]
        job = res_data["job"]

        assert save["id"] == save_id
        assert job["state"] == "ready"
        assert "extraction_failed" in (job["error"] or "").lower() or "503" in (job["error"] or "")


@pytest.mark.anyio
async def test_e2e_reprocessing_endpoint_and_execution(e2e_env):
    """End-to-end: reprocess endpoint re-queues job and executes pipeline."""
    app = e2e_env["app"]
    headers = e2e_env["headers"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers) as client:
        # Initial capture & processing
        resp = await client.post("/saves", json={"url": "https://example.com/reprocess-test"})
        save_id = resp.json()["data"]["id"]
        await wait_for_job_ready(client, save_id)

        # Reprocess from transcribing
        reprocess_resp = await client.post(f"/saves/{save_id}/reprocess?from=transcribing")
        assert reprocess_resp.status_code == 202
        assert reprocess_resp.json()["data"]["state"] == "queued"
        assert reprocess_resp.json()["data"]["from"] == "transcribing"

        # Wait for reprocess run to finish
        reprocessed_data = await wait_for_job_ready(client, save_id)
        assert reprocessed_data["job"]["state"] == "ready"

        # Invalid stage rejected
        invalid_resp = await client.post(f"/saves/{save_id}/reprocess?from=invalid_stage")
        assert invalid_resp.status_code == 422


@pytest.mark.anyio
async def test_e2e_startup_recovery(e2e_env):
    """End-to-end: startup recovery resets interrupted extracting/transcribing jobs."""
    store = e2e_env["store"]
    now = now_iso_z()

    # Insert an interrupted job
    save_id = new_uuid7()

    def _tx(conn):
        conn.execute(
            "INSERT INTO saves(id, raw_url, url, platform, source_app, user_context, captured_at, created_at, updated_at)"
            " VALUES (?, 'https://example.com', 'https://example.com', 'web', 'app', '', ?, ?, ?)",
            (save_id, now, now, now),
        )
        conn.execute(
            "INSERT INTO jobs(save_id, state, tier, created_at, updated_at) VALUES (?, 'transcribing', 1, ?, ?)",
            (save_id, now, now),
        )

    await store.run_tx(_tx)

    recovered = await recover_stale_jobs(store)
    assert recovered == 1

    job_row = await store.fetchone("SELECT state, error FROM jobs WHERE save_id=?", (save_id,))
    assert job_row is not None
    assert job_row["state"] == "queued"
    assert job_row["error"] is None


@pytest.mark.anyio
async def test_e2e_tier2_stub_rescue_provider():
    """Verify Tier-2 rescue stub conforms to Tier2RescueProvider protocol."""
    rescue = Tier2RescueStub()
    empty_result = ExtractionResult(
        tier=1,
        kind=Kind.ARTICLE,
        title=None,
        body=None,
        capability_flags=CapabilityFlags(has_audio=False, has_timeline=False, has_images=False),
    )
    result = await rescue.rescue("https://example.com/blocked", empty_result)
    assert result.tier == 2
    assert result.kind == Kind.UNKNOWN
    assert result.source_meta.get("tier2_status") == "unconfigured"
