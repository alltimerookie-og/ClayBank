"""Tests for Phase 3 Component 4.1: Local faster-whisper ASR Provider (ADR 0004, Rules.md §8).

Verifies protocol conformance, duration cap enforcement (600s), audio format checks,
path traversal rejection, media containment, lazy initialization, model reuse,
safe logging, error handling, timeouts, and temporary media isolation.
"""
from __future__ import annotations

import asyncio
import logging
import wave
from pathlib import Path
from typing import Any
from unittest.mock import patch
import pytest

from backend.asr.local import (
    FasterWhisperLocalProvider,
    probe_audio_duration,
    validate_audio_path_safety,
)
from backend.asr.protocol import ASRProvider
from backend.processing.media import IsolatedJobMedia


# --- Helpers & Mocks ---

class MockSegment:
    def __init__(self, text: str) -> None:
        self.text = text


class MockWhisperModel:
    def __init__(
        self,
        segments: list[MockSegment] | None = None,
        raise_on_transcribe: Exception | None = None,
    ) -> None:
        self.segments = segments if segments is not None else [
            MockSegment("This is a verified test transcription for local ASR.")
        ]
        self.raise_on_transcribe = raise_on_transcribe
        self.transcribe_calls: list[dict[str, Any]] = []

    def transcribe(self, audio_path: str, **kwargs: Any) -> tuple[list[MockSegment], Any]:
        if self.raise_on_transcribe:
            raise self.raise_on_transcribe
        self.transcribe_calls.append({"audio_path": audio_path, **kwargs})
        return self.segments, None


def create_test_wav(path: Path, duration_seconds: float = 1.0, framerate: int = 16000) -> Path:
    """Create a minimal valid PCM WAV file for deterministic testing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    nframes = int(duration_seconds * framerate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(b"\x00\x00" * nframes)
    return path


# --- Unit Tests: Validation & Probing ---

def test_protocol_conformance() -> None:
    """Verify FasterWhisperLocalProvider conforms to the ASRProvider protocol."""
    provider = FasterWhisperLocalProvider()
    assert isinstance(provider, ASRProvider)


def test_probe_valid_wav_duration(tmp_path: Path) -> None:
    """Verify probe_audio_duration correctly determines duration of a WAV file."""
    wav_path = tmp_path / "sample.wav"
    create_test_wav(wav_path, duration_seconds=2.5)
    duration = probe_audio_duration(wav_path)
    assert duration is not None
    assert abs(duration - 2.5) < 0.1


def test_probe_corrupt_audio_returns_none(tmp_path: Path) -> None:
    """Verify probe_audio_duration returns None on corrupt audio data."""
    corrupt_file = tmp_path / "corrupt.wav"
    corrupt_file.write_bytes(b"NOT_A_VALID_HEADER_DATA_12345")
    duration = probe_audio_duration(corrupt_file)
    assert duration is None


def test_validate_path_safety_within_job_dir(tmp_path: Path) -> None:
    """Verify validate_audio_path_safety passes for a valid file in an isolated job directory."""
    job_dir = tmp_path / "claybank" / "job_save123_abc"
    job_dir.mkdir(parents=True, exist_ok=True)
    audio_file = job_dir / "audio.wav"
    create_test_wav(audio_file)

    resolved = validate_audio_path_safety(audio_file, allowed_root=tmp_path / "claybank")
    assert resolved == audio_file.resolve()


def test_validate_path_safety_rejects_missing_file(tmp_path: Path) -> None:
    """Verify FileNotFoundError when the audio file does not exist."""
    missing = tmp_path / "claybank" / "job_123_abc" / "missing.wav"
    with pytest.raises(FileNotFoundError):
        validate_audio_path_safety(missing, allowed_root=tmp_path / "claybank")


def test_validate_path_safety_rejects_empty_file(tmp_path: Path) -> None:
    """Verify ValueError when the audio file is 0 bytes."""
    empty_file = tmp_path / "claybank" / "job_123_abc" / "empty.wav"
    empty_file.parent.mkdir(parents=True, exist_ok=True)
    empty_file.write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        validate_audio_path_safety(empty_file, allowed_root=tmp_path / "claybank")


def test_validate_path_safety_rejects_unsupported_format(tmp_path: Path) -> None:
    """Verify ValueError on unsupported media extensions."""
    text_file = tmp_path / "claybank" / "job_123_abc" / "audio.txt"
    text_file.parent.mkdir(parents=True, exist_ok=True)
    text_file.write_bytes(b"hello world")
    with pytest.raises(ValueError, match="Unsupported audio format"):
        validate_audio_path_safety(text_file, allowed_root=tmp_path / "claybank")


def test_validate_path_safety_rejects_path_traversal(tmp_path: Path) -> None:
    """Verify ValueError when attempting path traversal out of media root."""
    outside_file = tmp_path / "outside.wav"
    create_test_wav(outside_file)
    with pytest.raises(ValueError, match="outside ClayBank media directory"):
        validate_audio_path_safety(outside_file, allowed_root=tmp_path / "claybank")


def test_validate_path_safety_rejects_file_outside_job_dir(tmp_path: Path) -> None:
    """Verify ValueError when file is directly in media root rather than a job directory."""
    root_file = tmp_path / "claybank" / "stray.wav"
    root_file.parent.mkdir(parents=True, exist_ok=True)
    create_test_wav(root_file)
    with pytest.raises(ValueError, match="not inside an isolated job directory"):
        validate_audio_path_safety(root_file, allowed_root=tmp_path / "claybank")


# --- Integration Tests: Transcription Behavior ---

@pytest.mark.anyio
async def test_successful_transcription(tmp_path: Path) -> None:
    """Verify successful transcription returns plain string text."""
    media_root = tmp_path / "claybank"
    async with IsolatedJobMedia("save_101", base_dir=media_root) as job_dir:
        audio_file = job_dir / "audio.wav"
        create_test_wav(audio_file, duration_seconds=3.0)

        mock_model = MockWhisperModel([MockSegment("Hello ClayBank world.")])
        provider = FasterWhisperLocalProvider(allowed_media_dir=media_root, model=mock_model)

        transcript = await provider.transcribe(audio_file)

        assert isinstance(transcript, str)
        assert transcript == "Hello ClayBank world."
        assert len(mock_model.transcribe_calls) == 1
        assert mock_model.transcribe_calls[0]["beam_size"] == 5
        assert mock_model.transcribe_calls[0]["vad_filter"] is True


@pytest.mark.anyio
async def test_language_parameter_forwarding(tmp_path: Path) -> None:
    """Verify optional language parameter is passed to model."""
    media_root = tmp_path / "claybank"
    async with IsolatedJobMedia("save_102", base_dir=media_root) as job_dir:
        audio_file = job_dir / "audio.wav"
        create_test_wav(audio_file)

        mock_model = MockWhisperModel([MockSegment("Hola mundo.")])
        provider = FasterWhisperLocalProvider(allowed_media_dir=media_root, model=mock_model)

        transcript = await provider.transcribe(audio_file, language="es")
        assert transcript == "Hola mundo."
        assert mock_model.transcribe_calls[0]["language"] == "es"


@pytest.mark.anyio
async def test_empty_transcription_returns_empty_string(tmp_path: Path) -> None:
    """Verify empty segment generator returns an empty string honestly."""
    media_root = tmp_path / "claybank"
    async with IsolatedJobMedia("save_103", base_dir=media_root) as job_dir:
        audio_file = job_dir / "audio.wav"
        create_test_wav(audio_file)

        mock_model = MockWhisperModel(segments=[])
        provider = FasterWhisperLocalProvider(allowed_media_dir=media_root, model=mock_model)

        transcript = await provider.transcribe(audio_file)
        assert transcript == ""


@pytest.mark.anyio
async def test_no_speech_detected_returns_empty_string(tmp_path: Path) -> None:
    """Verify segments with only whitespace/silence return empty string."""
    media_root = tmp_path / "claybank"
    async with IsolatedJobMedia("save_104", base_dir=media_root) as job_dir:
        audio_file = job_dir / "audio.wav"
        create_test_wav(audio_file)

        mock_model = MockWhisperModel(segments=[MockSegment("   "), MockSegment("\n\t")])
        provider = FasterWhisperLocalProvider(allowed_media_dir=media_root, model=mock_model)

        transcript = await provider.transcribe(audio_file)
        assert transcript == ""


@pytest.mark.anyio
async def test_duration_cap_exactly_600_seconds_accepted(tmp_path: Path) -> None:
    """Verify audio of exactly 600.0 seconds is accepted."""
    media_root = tmp_path / "claybank"
    async with IsolatedJobMedia("save_105", base_dir=media_root) as job_dir:
        audio_file = job_dir / "audio.wav"
        create_test_wav(audio_file, duration_seconds=1.0)

        mock_model = MockWhisperModel([MockSegment("Boundary check.")])
        provider = FasterWhisperLocalProvider(allowed_media_dir=media_root, model=mock_model)

        with patch("backend.asr.local.probe_audio_duration", return_value=600.0):
            transcript = await provider.transcribe(audio_file)
            assert transcript == "Boundary check."


@pytest.mark.anyio
async def test_duration_cap_exceeded_rejected(tmp_path: Path) -> None:
    """Verify audio of 600.1 seconds is rejected before calling the model."""
    media_root = tmp_path / "claybank"
    async with IsolatedJobMedia("save_106", base_dir=media_root) as job_dir:
        audio_file = job_dir / "audio.wav"
        create_test_wav(audio_file, duration_seconds=1.0)

        mock_model = MockWhisperModel([MockSegment("Should never run.")])
        provider = FasterWhisperLocalProvider(allowed_media_dir=media_root, model=mock_model)

        with patch("backend.asr.local.probe_audio_duration", return_value=600.1):
            with pytest.raises(ValueError, match="exceeds maximum allowed cap"):
                await provider.transcribe(audio_file)

        assert len(mock_model.transcribe_calls) == 0


@pytest.mark.anyio
async def test_zero_duration_rejected(tmp_path: Path) -> None:
    """Verify audio with 0 duration is rejected before calling the model."""
    media_root = tmp_path / "claybank"
    async with IsolatedJobMedia("save_107", base_dir=media_root) as job_dir:
        audio_file = job_dir / "audio.wav"
        create_test_wav(audio_file)

        mock_model = MockWhisperModel()
        provider = FasterWhisperLocalProvider(allowed_media_dir=media_root, model=mock_model)

        with patch("backend.asr.local.probe_audio_duration", return_value=0.0):
            with pytest.raises(ValueError, match="duration"):
                await provider.transcribe(audio_file)

        assert len(mock_model.transcribe_calls) == 0


@pytest.mark.anyio
async def test_missing_duration_metadata_rejected(tmp_path: Path) -> None:
    """Verify audio with missing duration metadata is rejected safely."""
    media_root = tmp_path / "claybank"
    async with IsolatedJobMedia("save_108", base_dir=media_root) as job_dir:
        audio_file = job_dir / "audio.wav"
        create_test_wav(audio_file)

        mock_model = MockWhisperModel()
        provider = FasterWhisperLocalProvider(allowed_media_dir=media_root, model=mock_model)

        with patch("backend.asr.local.probe_audio_duration", return_value=None):
            with pytest.raises(ValueError, match="Unable to determine media duration"):
                await provider.transcribe(audio_file)

        assert len(mock_model.transcribe_calls) == 0


@pytest.mark.anyio
async def test_model_initialization_failure(tmp_path: Path) -> None:
    """Verify RuntimeError is raised when model constructor fails."""
    media_root = tmp_path / "claybank"
    async with IsolatedJobMedia("save_109", base_dir=media_root) as job_dir:
        audio_file = job_dir / "audio.wav"
        create_test_wav(audio_file)

        provider = FasterWhisperLocalProvider(allowed_media_dir=media_root)

        with patch("faster_whisper.WhisperModel", side_effect=Exception("Weights corrupted")):
            with pytest.raises(RuntimeError, match="Failed to initialize faster-whisper model"):
                await provider.transcribe(audio_file)


@pytest.mark.anyio
async def test_transcription_runtime_exception(tmp_path: Path) -> None:
    """Verify RuntimeError is raised when model.transcribe raises an exception."""
    media_root = tmp_path / "claybank"
    async with IsolatedJobMedia("save_110", base_dir=media_root) as job_dir:
        audio_file = job_dir / "audio.wav"
        create_test_wav(audio_file)

        mock_model = MockWhisperModel(raise_on_transcribe=RuntimeError("CUDA out of memory simulation"))
        provider = FasterWhisperLocalProvider(allowed_media_dir=media_root, model=mock_model)

        with pytest.raises(RuntimeError, match="ASR transcription failed"):
            await provider.transcribe(audio_file)


@pytest.mark.anyio
async def test_timeout_behavior(tmp_path: Path) -> None:
    """Verify timeout cancels await without uncaught exceptions leaking."""
    media_root = tmp_path / "claybank"
    async with IsolatedJobMedia("save_111", base_dir=media_root) as job_dir:
        audio_file = job_dir / "audio.wav"
        create_test_wav(audio_file)

        class HangingModel:
            def transcribe(self, *args: Any, **kwargs: Any) -> Any:
                import time
                time.sleep(1.0)
                return [MockSegment("late")], None

        provider = FasterWhisperLocalProvider(allowed_media_dir=media_root, model=HangingModel())

        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.05):
                await provider.transcribe(audio_file)


@pytest.mark.anyio
async def test_cancellation_behavior(tmp_path: Path) -> None:
    """Verify cancellation propagates cleanly to the caller."""
    media_root = tmp_path / "claybank"
    async with IsolatedJobMedia("save_112", base_dir=media_root) as job_dir:
        audio_file = job_dir / "audio.wav"
        create_test_wav(audio_file)

        class HangingModel:
            def transcribe(self, *args: Any, **kwargs: Any) -> Any:
                import time
                time.sleep(1.0)
                return [MockSegment("late")], None

        provider = FasterWhisperLocalProvider(allowed_media_dir=media_root, model=HangingModel())

        task = asyncio.create_task(provider.transcribe(audio_file))
        await asyncio.sleep(0.02)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.anyio
async def test_safe_logging_never_exposes_transcript(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify transcript text is never logged to application logs."""
    media_root = tmp_path / "claybank"
    secret_text = "SECRET_PATIENT_MEDICAL_RECORD_998877"

    async with IsolatedJobMedia("save_113", base_dir=media_root) as job_dir:
        audio_file = job_dir / "audio.wav"
        create_test_wav(audio_file)

        mock_model = MockWhisperModel([MockSegment(secret_text)])
        provider = FasterWhisperLocalProvider(allowed_media_dir=media_root, model=mock_model)

        with caplog.at_level(logging.INFO):
            result = await provider.transcribe(audio_file)

        assert result == secret_text
        log_text = caplog.text

        # Bounded metadata is logged, but transcript text is strictly excluded
        assert "Local ASR transcription completed" in log_text
        assert "model=small" in log_text
        assert secret_text not in log_text


@pytest.mark.anyio
async def test_model_reuse_across_calls(tmp_path: Path) -> None:
    """Verify the same model instance is reused across multiple transcription calls."""
    media_root = tmp_path / "claybank"
    async with IsolatedJobMedia("save_114", base_dir=media_root) as job_dir:
        audio1 = job_dir / "audio1.wav"
        audio2 = job_dir / "audio2.wav"
        create_test_wav(audio1)
        create_test_wav(audio2)

        mock_model = MockWhisperModel([MockSegment("Segment 1")])
        provider = FasterWhisperLocalProvider(allowed_media_dir=media_root, model=mock_model)

        res1 = await provider.transcribe(audio1)
        res2 = await provider.transcribe(audio2)

        assert res1 == "Segment 1"
        assert res2 == "Segment 1"
        assert len(mock_model.transcribe_calls) == 2


@pytest.mark.anyio
async def test_lazy_initialization(tmp_path: Path) -> None:
    """Verify model is not initialized during provider instantiation."""
    provider = FasterWhisperLocalProvider(model_size="small")
    assert provider._model is None


@pytest.mark.anyio
async def test_temporary_media_cleanup_on_failure(tmp_path: Path) -> None:
    """Verify IsolatedJobMedia cleans up completely even when transcription raises an error."""
    media_root = tmp_path / "claybank"
    job_dir_path: Path | None = None

    try:
        async with IsolatedJobMedia("save_115", base_dir=media_root) as job_dir:
            job_dir_path = job_dir
            audio_file = job_dir / "audio.wav"
            create_test_wav(audio_file)
            assert audio_file.exists()

            mock_model = MockWhisperModel(raise_on_transcribe=RuntimeError("Failing"))
            provider = FasterWhisperLocalProvider(allowed_media_dir=media_root, model=mock_model)

            await provider.transcribe(audio_file)
    except RuntimeError:
        pass

    assert job_dir_path is not None
    assert not job_dir_path.exists()  # Completely cleaned up
