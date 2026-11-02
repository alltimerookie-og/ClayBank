"""Tests for Phase 3 Component 4.2: ASR Provider Selection (ADR 0004, Architecture §4.2).

Verifies provider factory selection, explicit Muse Voice blocking, availability checks,
and protocol conformance.
"""
from __future__ import annotations

from unittest.mock import patch
import pytest

from backend.asr.factory import (
    ASRProviderType,
    MUSE_VOICE_BLOCKED_REASON,
    get_asr_provider,
    is_faster_whisper_available,
)
from backend.asr.local import FasterWhisperLocalProvider
from backend.asr.protocol import ASRProvider


def test_select_local_provider_success() -> None:
    """Verify selecting 'local' returns an instance conforming to ASRProvider."""
    provider = get_asr_provider(ASRProviderType.LOCAL)
    assert isinstance(provider, ASRProvider)
    assert isinstance(provider, FasterWhisperLocalProvider)
    assert provider.model_size == "small"
    assert provider.device == "cpu"
    assert provider.compute_type == "int8"


def test_select_local_provider_string_alias() -> None:
    """Verify string aliases for local provider ('local', 'whisper', 'faster-whisper')."""
    for alias in ("local", "whisper", "faster-whisper"):
        provider = get_asr_provider(alias)
        assert isinstance(provider, FasterWhisperLocalProvider)


def test_select_local_provider_with_injected_model() -> None:
    """Verify local provider accepts an injected mock model."""
    mock_model = object()
    provider = get_asr_provider("local", local_model=mock_model)
    assert isinstance(provider, FasterWhisperLocalProvider)
    assert provider._model is mock_model


def test_select_muse_voice_explicitly_blocked() -> None:
    """Verify requesting Muse Voice raises RuntimeError with the exact blocked status."""
    for muse_alias in ("muse", "muse_voice", ASRProviderType.MUSE):
        with pytest.raises(RuntimeError) as exc_info:
            get_asr_provider(muse_alias)
        assert MUSE_VOICE_BLOCKED_REASON in str(exc_info.value)


def test_select_unknown_provider_raises_value_error() -> None:
    """Verify requesting an unsupported provider raises ValueError."""
    with pytest.raises(ValueError, match="Unknown or unsupported ASR provider type"):
        get_asr_provider("speculative_cloud_provider")


def test_local_provider_unavailable_when_dependency_missing() -> None:
    """Verify RuntimeError is raised if faster-whisper is missing when requesting local provider."""
    with patch("backend.asr.factory.is_faster_whisper_available", return_value=False):
        with pytest.raises(RuntimeError, match="faster-whisper is not installed"):
            get_asr_provider("local", local_model=None)


def test_is_faster_whisper_available_detection() -> None:
    """Verify is_faster_whisper_available detects installed package."""
    assert is_faster_whisper_available() is True

    with patch.dict("sys.modules", {"faster_whisper": None}):
        with patch("builtins.__import__", side_effect=ImportError("No module named faster_whisper")):
            assert is_faster_whisper_available() is False
