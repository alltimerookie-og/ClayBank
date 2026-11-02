"""ASR provider factory and selection seam (ADR 0004, Architecture §4.2).

Selects and provides speech-to-text engines conforming to ASRProvider.
Enforces that Muse Voice Cloud ASR is explicitly BLOCKED pending official API specifications.
"""
from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

from backend.asr.local import FasterWhisperLocalProvider
from backend.asr.protocol import ASRProvider

logger = logging.getLogger(__name__)

MUSE_VOICE_BLOCKED_REASON = "BLOCKED: Official API specification required."


class ASRProviderType(StrEnum):
    LOCAL = "local"
    MUSE = "muse"


def is_faster_whisper_available() -> bool:
    """Check if the faster-whisper package is installed and importable."""
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def get_asr_provider(
    provider_type: str | ASRProviderType = ASRProviderType.LOCAL,
    *,
    model_size: str = "small",
    device: str = "cpu",
    compute_type: str = "int8",
    local_model: Any = None,
) -> ASRProvider:
    """Select and instantiate an ASR provider conforming to ASRProvider.

    Args:
        provider_type: Provider selection ('local' or 'muse').
        model_size: Faster-whisper model size (defaults to 'small').
        device: Compute device ('cpu').
        compute_type: Quantization type ('int8').
        local_model: Optional pre-loaded model or mock instance for testing.

    Returns:
        ASRProvider: Instantiated provider.

    Raises:
        RuntimeError: If the requested provider is blocked, unavailable, or unsupported.
    """
    prov_str = str(provider_type).lower()

    if prov_str in (ASRProviderType.MUSE, "muse", "muse_voice"):
        logger.warning("Attempted to select Muse Voice cloud ASR: %s", MUSE_VOICE_BLOCKED_REASON)
        raise RuntimeError(f"Muse Voice Cloud ASR is {MUSE_VOICE_BLOCKED_REASON}")

    if prov_str in (ASRProviderType.LOCAL, "local", "whisper", "faster-whisper"):
        if local_model is None and not is_faster_whisper_available():
            raise RuntimeError("Local ASR provider unavailable: faster-whisper is not installed")
        return FasterWhisperLocalProvider(
            model_size=model_size,
            device=device,
            compute_type=compute_type,
            model=local_model,
        )

    raise ValueError(f"Unknown or unsupported ASR provider type: '{provider_type}'")
