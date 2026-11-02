"""Unit tests for Phase 3 extraction contracts, protocols, and configuration (Task 1).

Runnable plain (python tests/test_phase3_contracts.py) and via pytest.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import jsonschema
import pytest
from pydantic import ValidationError

from backend.config import settings
from backend.contracts.enums import Kind
from backend.contracts.extraction import CapabilityFlags, ExtractionResult
from backend.extraction.protocol import Extractor, Tier2RescueProvider
from backend.asr.protocol import ASRProvider


def _load_schema() -> dict:
    schema_path = REPO_ROOT / "Docs" / "api" / "schemas" / "extraction-result.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_fixtures_conform_to_extraction_result_contract():
    schema = _load_schema()
    fixtures_path = REPO_ROOT / "Docs" / "api" / "fixtures" / "extraction-result.fixtures.json"
    data = json.loads(fixtures_path.read_text(encoding="utf-8"))

    for item in data.get("valid", []):
        # 1. JSON Schema validation
        jsonschema.validate(instance=item, schema=schema)
        # 2. Pydantic model parsing
        model = ExtractionResult.model_validate(item)
        assert model.tier in (1, 2)
        assert model.kind in (Kind.VIDEO, Kind.ARTICLE, Kind.UNKNOWN)
        # 3. Model dump conforms back to schema
        dumped = model.model_dump(mode="json")
        jsonschema.validate(instance=dumped, schema=schema)


def test_video_invariant_has_audio_validation():
    # Schema allOf invariant: if kind == video, has_audio must be true
    # 1. Default creation automatically defaults has_audio=True for video
    res = ExtractionResult(kind=Kind.VIDEO, title="Test Video")
    assert res.capability_flags.has_audio is True

    # 2. Explicit has_audio=True is valid
    res_explicit = ExtractionResult(
        kind=Kind.VIDEO,
        capability_flags=CapabilityFlags(has_audio=True),
        title="Test Video 2",
    )
    assert res_explicit.capability_flags.has_audio is True

    # 3. Explicit has_audio=False for video violates the schema invariant -> raises ValidationError
    with pytest.raises(ValidationError) as exc_info:
        ExtractionResult(
            kind=Kind.VIDEO,
            capability_flags=CapabilityFlags(has_audio=False),
            title="Invalid Video",
        )
    assert "has_audio=True" in str(exc_info.value)

    # 4. Articles do not default to has_audio
    res3 = ExtractionResult(kind=Kind.ARTICLE, title="Test Article", body="Some text")
    assert res3.capability_flags.has_audio is False


def test_extra_fields_forbidden():
    # Top-level unexpected fields are forbidden to prevent silent data loss (extras belong in source_meta)
    with pytest.raises(ValidationError):
        ExtractionResult(kind=Kind.UNKNOWN, unexpected_field="bad")

    # Extra fields on CapabilityFlags are also forbidden
    with pytest.raises(ValidationError):
        CapabilityFlags(unexpected_flag=True)

    # Platform extras placed inside source_meta are accepted
    valid_with_meta = ExtractionResult(
        kind=Kind.UNKNOWN,
        source_meta={"custom_channel_id": "12345", "thumbnail_url": "https://example.com/thumb.jpg"},
    )
    assert valid_with_meta.source_meta["custom_channel_id"] == "12345"


def test_published_iso_date_validation():
    # 1. Valid ISO date YYYY-MM-DD
    r1 = ExtractionResult(kind=Kind.ARTICLE, published="2026-10-03")
    assert r1.published == "2026-10-03"

    # 2. None / omitted is valid
    r2 = ExtractionResult(kind=Kind.ARTICLE, published=None)
    assert r2.published is None

    # 3. Invalid dates raise ValidationError (per format: date)
    for bad_date in ("invalid-date", "2026/10/03", "October 3, 2026", "2026-13-45", "2026-02-30"):
        with pytest.raises(ValidationError):
            ExtractionResult(kind=Kind.ARTICLE, published=bad_date)


def test_adr_0002_tier2_rescue_logic():
    # 1. Video:
    # - Title present, no transcript -> Tier 1 success, no rescue
    v1 = ExtractionResult(kind=Kind.VIDEO, title="Some Reel", body=None, transcript_available=False)
    assert v1.needs_tier2_rescue() is False

    # - Transcript present, no title -> Tier 1 success, no rescue
    v2 = ExtractionResult(kind=Kind.VIDEO, title=None, body="Spoken words", transcript_available=True)
    assert v2.needs_tier2_rescue() is False

    # - Missing both title and transcript -> fires Tier 2 rescue
    v3 = ExtractionResult(kind=Kind.VIDEO, title=None, body=None, transcript_available=False)
    assert v3.needs_tier2_rescue() is True

    # 2. Article:
    # - Body present -> Tier 1 success, no rescue
    a1 = ExtractionResult(kind=Kind.ARTICLE, title=None, body="Article paragraph content")
    assert a1.needs_tier2_rescue() is False

    # - No body -> fires Tier 2 rescue
    a2 = ExtractionResult(kind=Kind.ARTICLE, title="Article Title", body=None)
    assert a2.needs_tier2_rescue() is True

    # 3. Unknown:
    # - Title present -> no rescue
    u1 = ExtractionResult(kind=Kind.UNKNOWN, title="Page Title", body=None)
    assert u1.needs_tier2_rescue() is False

    # - Body present -> no rescue
    u2 = ExtractionResult(kind=Kind.UNKNOWN, title=None, body="Page content")
    assert u2.needs_tier2_rescue() is False

    # - Missing both -> fires Tier 2 rescue
    u3 = ExtractionResult(kind=Kind.UNKNOWN, title=None, body=None)
    assert u3.needs_tier2_rescue() is True


def test_degraded_factory_creates_schema_valid_result():
    schema = _load_schema()
    deg = ExtractionResult.degraded(
        kind=Kind.UNKNOWN,
        title="Blocked Page",
        raw_url="https://example.com/blocked",
        source_meta={"error_hint": "403 Forbidden"},
    )
    assert deg.tier == 1
    assert deg.kind == Kind.UNKNOWN
    assert deg.title == "Blocked Page"
    assert deg.source_meta.get("raw_url") == "https://example.com/blocked"
    jsonschema.validate(instance=deg.model_dump(mode="json"), schema=schema)


def test_empty_factory_creates_schema_valid_result():
    schema = _load_schema()
    empty = ExtractionResult.empty(kind=Kind.VIDEO)
    assert empty.tier == 1
    assert empty.kind == Kind.VIDEO
    assert empty.capability_flags.has_audio is True
    jsonschema.validate(instance=empty.model_dump(mode="json"), schema=schema)


def test_extractor_protocol_conformance():
    class DummyExtractor:
        async def extract(self, url: str, platform: str) -> ExtractionResult:
            return ExtractionResult.empty()

    class IncompleteExtractor:
        pass

    assert isinstance(DummyExtractor(), Extractor)
    assert not isinstance(IncompleteExtractor(), Extractor)


def test_tier2_rescue_protocol_conformance():
    class DummyRescueProvider:
        async def rescue(self, url: str, initial_result: ExtractionResult) -> ExtractionResult:
            return initial_result

    class IncompleteRescueProvider:
        pass

    assert isinstance(DummyRescueProvider(), Tier2RescueProvider)
    assert not isinstance(IncompleteRescueProvider(), Tier2RescueProvider)


def test_asr_provider_protocol_conformance():
    class DummyASRProvider:
        async def transcribe(self, audio_path: Path, language: str | None = None) -> str:
            return "Sample transcript"

    class IncompleteASRProvider:
        pass

    assert isinstance(DummyASRProvider(), ASRProvider)
    assert not isinstance(IncompleteASRProvider(), ASRProvider)


def test_phase3_configuration_budgets():
    assert settings.ASR_DURATION_CAP_SECONDS == 600
    assert settings.EXTRACTION_TIMEOUT_SECONDS == 30
    assert settings.JOB_HARD_TIMEOUT_SECONDS == 120


if __name__ == "__main__":
    test_fixtures_conform_to_extraction_result_contract()
    test_video_invariant_has_audio_validation()
    test_extra_fields_forbidden()
    test_published_iso_date_validation()
    test_adr_0002_tier2_rescue_logic()
    test_degraded_factory_creates_schema_valid_result()
    test_empty_factory_creates_schema_valid_result()
    test_extractor_protocol_conformance()
    test_tier2_rescue_protocol_conformance()
    test_asr_provider_protocol_conformance()
    test_phase3_configuration_budgets()
    print("phase3 contracts tests: OK")
