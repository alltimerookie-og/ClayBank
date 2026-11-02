"""Local ASR provider using faster-whisper (ADR 0004, Architecture §4.2, PRD §5.2).

Performs automatic speech recognition on temporary audio files using a local CPU-only
Whisper model with strict duration caps, media isolation, and guaranteed scrubbing.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Any

from backend.config import settings
from backend.processing.media import get_base_media_dir

logger = logging.getLogger(__name__)

SUPPORTED_AUDIO_EXTENSIONS = frozenset({
    ".wav",
    ".mp3",
    ".m4a",
    ".aac",
    ".ogg",
    ".flac",
    ".opus",
    ".webm",
})


def probe_audio_duration(audio_path: Path) -> float | None:
    """Probe audio duration in seconds without decoding full media frames into memory.

    Uses PyAV (installed with faster-whisper) to inspect container and stream metadata.
    Falls back to the standard library wave module for WAV files.

    Args:
        audio_path: Path to the audio file.

    Returns:
        float | None: Duration in seconds, or None if duration is missing or unreadable.
    """
    try:
        import av
        with av.open(str(audio_path)) as container:
            if container.duration is not None and container.duration > 0:
                return float(container.duration) / float(av.time_base)
            if container.streams.audio:
                stream = container.streams.audio[0]
                if stream.duration is not None and stream.time_base is not None and stream.duration > 0:
                    return float(stream.duration * stream.time_base)
    except Exception:
        pass

    # Secondary fallback for WAV files
    if audio_path.suffix.lower() == ".wav":
        try:
            import wave
            with wave.open(str(audio_path), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate > 0 and frames > 0:
                    return float(frames) / float(rate)
        except Exception:
            pass

    return None


def validate_audio_path_safety(audio_path: Path, allowed_root: Path | None = None) -> Path:
    """Validate that audio file exists, is inside a ClayBank isolated job directory, and is supported.

    Args:
        audio_path: Path to the target audio file.
        allowed_root: Optional root directory override (defaults to get_base_media_dir()).

    Returns:
        Path: Resolved absolute path.

    Raises:
        FileNotFoundError: If the audio file does not exist.
        ValueError: If path traversal is detected, file is outside a job directory,
                    format is unsupported, or file is empty.
    """
    if not isinstance(audio_path, (str, Path)) or not str(audio_path).strip():
        raise ValueError("Invalid audio path: path must be a non-empty string or Path")

    path = Path(audio_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {path.name}")

    resolved = path.resolve()
    root = (allowed_root if allowed_root is not None else get_base_media_dir()).resolve()

    # Enforce path containment within media root
    try:
        rel = resolved.relative_to(root)
    except ValueError:
        raise ValueError("Audio path traversal: file is outside ClayBank media directory")

    # Enforce that the file is located inside a job_* subdirectory
    if len(rel.parts) < 2 or not rel.parts[0].startswith("job_"):
        raise ValueError("Audio path traversal: file is not inside an isolated job directory")

    # Enforce supported audio format extension
    ext = resolved.suffix.lower()
    if ext not in SUPPORTED_AUDIO_EXTENSIONS:
        raise ValueError(f"Unsupported audio format: '{ext}'")

    # Enforce non-empty file
    if resolved.stat().st_size == 0:
        raise ValueError("Audio file is empty (0 bytes)")

    return resolved


class FasterWhisperLocalProvider:
    """Local ASR provider conforming to ASRProvider using faster-whisper.

    Configured for CPU-only execution with 'small' model and int8 quantization.
    Model initialization is lazy and cached across calls to avoid duplicate memory usage.
    """

    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        cpu_threads: int | None = None,
        allowed_media_dir: Path | None = None,
        model: Any = None,
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads or min(4, os.cpu_count() or 1)
        self._allowed_media_dir = allowed_media_dir
        self._model = model
        self._inference_lock = asyncio.Lock()

    def _get_model(self) -> Any:
        """Lazily initialize or return the cached WhisperModel instance."""
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("faster-whisper is not installed or available") from exc

        try:
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=self.cpu_threads,
            )
            return self._model
        except Exception as exc:
            raise RuntimeError(
                f"Failed to initialize faster-whisper model '{self.model_size}': {exc}"
            ) from exc

    async def transcribe(self, audio_path: Path, language: str | None = None) -> str:
        """Transcribe a temporary audio file and return plain transcript text.

        Enforces audio existence, isolation containment, duration caps (600s),
        and runs synchronous inference off the event loop.

        Args:
            audio_path: Path to the local temporary audio file.
            language: Optional language hint (e.g. 'en', 'es').

        Returns:
            str: Plain text transcript.

        Raises:
            FileNotFoundError: If the audio file does not exist.
            ValueError: If audio validation, format, or duration cap fails.
            RuntimeError: If model initialization or transcription fails.
        """
        # 1. Validate audio path, containment, format, and size
        safe_path = validate_audio_path_safety(audio_path, allowed_root=self._allowed_media_dir)

        # 2. Probe and validate duration before invoking the model
        duration = probe_audio_duration(safe_path)
        if duration is None or duration <= 0:
            raise ValueError("Unable to determine media duration or audio contains no valid audio frames")

        cap = float(settings.ASR_DURATION_CAP_SECONDS)
        if duration > cap:
            raise ValueError(f"Audio duration ({duration:.1f}s) exceeds maximum allowed cap ({cap}s)")

        # 3. Lazily initialize model
        model = self._get_model()

        # 4. Execute transcription off the event loop under inference lock
        # Serializes execution on CPU hardware to prevent resource exhaustion and race conditions.
        # Note on Python timeout/cancellation limitation:
        # asyncio.to_thread() awaits a worker thread in Python's default thread pool.
        # Cancelling the coroutine does not forcibly terminate the underlying CTranslate2
        # C++ native execution thread. Safety is preserved because the worker function
        # is strictly read-only, produces no disk side-effects, and does not mutate job state.
        async with self._inference_lock:
            try:
                transcript = await asyncio.to_thread(
                    self._run_transcription_sync,
                    model,
                    str(safe_path),
                    language,
                )
            except Exception as err:
                logger.warning(
                    "Local ASR transcription failed: model=%s reason=%s",
                    self.model_size,
                    type(err).__name__,
                )
                raise RuntimeError(f"ASR transcription failed: {type(err).__name__}") from err

        logger.info(
            "Local ASR transcription completed: model=%s duration=%.1fs output_chars=%d",
            self.model_size,
            duration,
            len(transcript),
        )
        return transcript

    def _run_transcription_sync(
        self,
        model: Any,
        audio_path_str: str,
        language: str | None,
    ) -> str:
        """Synchronously execute faster-whisper transcribe in a worker thread."""
        kwargs: dict[str, Any] = {
            "beam_size": 5,
            "vad_filter": True,
        }
        if language:
            kwargs["language"] = language

        segments, _info = model.transcribe(audio_path_str, **kwargs)

        parts: list[str] = []
        for segment in segments:
            text = getattr(segment, "text", "")
            if text and text.strip():
                parts.append(text.strip())

        joined = " ".join(parts)
        return re.sub(r"\s+", " ", joined).strip()
