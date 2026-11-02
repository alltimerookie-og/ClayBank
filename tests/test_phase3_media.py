"""Tests for Phase 3 Task 2: Temporary Media Isolation and Cleanup Context Manager.

Enforces ADR 0004 ("Never persist media: temp files scrubbed on success and failure;
crashed job leaves nothing behind").
"""
from __future__ import annotations

import asyncio
from pathlib import Path
import shutil
from unittest.mock import patch
import pytest

from backend.processing.media import IsolatedJobMedia, get_base_media_dir


@pytest.mark.anyio
async def test_media_scrubbed_on_normal_exit(tmp_path: Path) -> None:
    """Verify that temporary directories and media files are completely removed on normal exit."""
    save_id = "0192d6e3-f8a1-7000-8000-000000000001"
    captured_dir: Path | None = None

    async with IsolatedJobMedia(save_id, base_dir=tmp_path) as job_dir:
        captured_dir = job_dir
        assert captured_dir.exists()
        assert captured_dir.is_dir()

        # Write mock transient media
        audio_file = captured_dir / "temp_audio.mp3"
        audio_file.write_bytes(b"ID3mockaudiobytes" * 100)
        assert audio_file.exists()

        # Write generated temp file via helper
        helper_file = IsolatedJobMedia(save_id, base_dir=tmp_path).create_temp_file
        # Calling on the active context's instance:
        active_helper = IsolatedJobMedia(save_id, base_dir=tmp_path)
        active_helper.dir = job_dir
        temp_file = active_helper.create_temp_file(suffix=".mp4")
        temp_file.write_bytes(b"mockvideobytes")
        assert temp_file.exists()

    # Once exited, the directory and all files must be completely wiped
    assert captured_dir is not None
    assert not captured_dir.exists()


@pytest.mark.anyio
async def test_media_scrubbed_on_exception(tmp_path: Path) -> None:
    """Verify that temporary media is scrubbed even when an unhandled exception occurs."""
    save_id = "test-error-job-123"
    captured_dir: Path | None = None

    with pytest.raises(RuntimeError, match="Extraction crash"):
        async with IsolatedJobMedia(save_id, base_dir=tmp_path) as job_dir:
            captured_dir = job_dir
            assert captured_dir.exists()
            (job_dir / "transient.wav").write_bytes(b"RIFFmockwav")
            raise RuntimeError("Extraction crash")

    assert captured_dir is not None
    assert not captured_dir.exists()


@pytest.mark.anyio
async def test_media_scrubbed_on_cancellation(tmp_path: Path) -> None:
    """Verify that temporary media is scrubbed when an asyncio task is cancelled."""
    save_id = "test-cancel-job-456"
    captured_dir: Path | None = None
    started_event = asyncio.Event()

    async def long_running_task() -> None:
        nonlocal captured_dir
        async with IsolatedJobMedia(save_id, base_dir=tmp_path) as job_dir:
            captured_dir = job_dir
            (job_dir / "streaming_audio.part").write_bytes(b"partial audio bytes")
            started_event.set()
            # Sleep indefinitely until cancelled
            await asyncio.sleep(100)

    task = asyncio.create_task(long_running_task())
    await started_event.wait()

    assert captured_dir is not None
    assert captured_dir.exists()

    # Cancel the running task
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Verified scrubbed after cancellation
    assert not captured_dir.exists()


@pytest.mark.anyio
async def test_media_scrubbed_on_timeout(tmp_path: Path) -> None:
    """Verify that temporary media is scrubbed when a task times out."""
    save_id = "test-timeout-job-789"
    captured_dir: Path | None = None

    async def stalled_job() -> None:
        nonlocal captured_dir
        async with IsolatedJobMedia(save_id, base_dir=tmp_path) as job_dir:
            captured_dir = job_dir
            (job_dir / "stalled.mp4").write_bytes(b"stalled content")
            await asyncio.sleep(5)

    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.05):
            await stalled_job()

    assert captured_dir is not None
    assert not captured_dir.exists()


@pytest.mark.anyio
async def test_concurrent_media_isolation(tmp_path: Path) -> None:
    """Verify that concurrent jobs operate in disjoint directories and cannot delete each other's files."""
    save_id_a = "save-concurrent-001"
    save_id_b = "save-concurrent-002"

    dir_a_captured: Path | None = None
    dir_b_captured: Path | None = None

    barrier_entered = asyncio.Event()
    barrier_job_a_done = asyncio.Event()

    async def worker_a() -> None:
        nonlocal dir_a_captured
        async with IsolatedJobMedia(save_id_a, base_dir=tmp_path) as job_dir:
            dir_a_captured = job_dir
            (job_dir / "audio_a.mp3").write_bytes(b"content a")
            barrier_entered.set()
            # Wait until worker b confirms it is running
            await asyncio.sleep(0.01)
        # Worker A has exited and cleaned up
        barrier_job_a_done.set()

    async def worker_b() -> None:
        nonlocal dir_b_captured
        async with IsolatedJobMedia(save_id_b, base_dir=tmp_path) as job_dir:
            dir_b_captured = job_dir
            (job_dir / "audio_b.mp3").write_bytes(b"content b")
            await barrier_entered.wait()
            # Wait until worker A completes and cleans up
            await barrier_job_a_done.wait()

            # Worker B's directory must STILL exist and its content must be intact!
            assert job_dir.exists()
            assert (job_dir / "audio_b.mp3").read_bytes() == b"content b"

    await asyncio.gather(worker_a(), worker_b())

    assert dir_a_captured is not None and not dir_a_captured.exists()
    assert dir_b_captured is not None and not dir_b_captured.exists()


def test_save_id_validation_prevents_path_traversal() -> None:
    """Verify that invalid save_id with traversal attempts are rejected."""
    with pytest.raises(ValueError, match="Invalid save_id"):
        IsolatedJobMedia("../../../evil")

    with pytest.raises(ValueError, match="Invalid save_id"):
        IsolatedJobMedia("save/with/slashes")

    with pytest.raises(ValueError, match="non-empty string"):
        IsolatedJobMedia("")


@pytest.mark.anyio
async def test_temp_file_creation_and_traversal_prevention(tmp_path: Path) -> None:
    """Verify safe temporary file generation and path traversal prevention within job directory."""
    media = IsolatedJobMedia("safe-job-123", base_dir=tmp_path)

    # Calling before entering context raises RuntimeError
    with pytest.raises(RuntimeError, match="Cannot create temporary file before entering"):
        media.create_temp_file()

    async with media as job_dir:
        # Generated temp file
        f1 = media.create_temp_file(suffix=".m4a")
        assert f1.parent == job_dir
        assert f1.name.endswith(".m4a")

        # Explicit safe file
        f2 = media.create_temp_file("custom.txt")
        assert f2 == job_dir / "custom.txt"

        # Traversal attempt must be rejected
        with pytest.raises(ValueError, match="Path traversal detected"):
            media.create_temp_file("../escaped.txt")


@pytest.mark.anyio
async def test_cleanup_retry_on_permission_error(tmp_path: Path) -> None:
    """Verify that cleanup retries when encountering PermissionError."""
    media = IsolatedJobMedia("perm-test-job", base_dir=tmp_path)
    async with media as job_dir:
        test_file = job_dir / "locked.tmp"
        test_file.write_bytes(b"test")

    # Manually re-enter and mock initial shutil.rmtree failure
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "dummy.txt").write_bytes(b"data")

    original_rmtree = shutil.rmtree
    call_count = 0

    def mock_rmtree(path, ignore_errors=False):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise PermissionError("Access denied (simulated lock)")
        return original_rmtree(path, ignore_errors=ignore_errors)

    with patch("backend.processing.media.shutil.rmtree", side_effect=mock_rmtree):
        media.cleanup()

    assert not job_dir.exists()
    assert call_count >= 2
