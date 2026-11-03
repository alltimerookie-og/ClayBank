"""Focused tests for full pipeline orchestration."""

from pathlib import Path

from fastapi.testclient import TestClient

from Backend.extraction.result import ExtractionResult
from Backend.main import app
from Backend.processing.orchestrator import ExtractionOrchestrator
from Backend.processing.pipeline import PipelineService
from Backend.store.database import Database


HEADERS = {
    "Authorization": "Bearer DEV_TOKEN",
    "X-Device-Id": "test-device",
}


class StaticVideo:
    """Deterministic video metadata source."""

    def fetch(self, url: str) -> dict:
        """Return fixed video metadata."""
        del url
        return {"title": "Clip", "channel": "channel", "duration": 42, "upload_date": "20261003"}


class StaticTranscriber:
    """Deterministic transcription source."""

    def transcribe(self, media, **kwargs) -> tuple[str | None, str]:
        """Return fixed transcript text."""
        del media, kwargs
        return "hello world", "multimodal"


def make_client(tmp_path: Path) -> TestClient:
    """Build a test client with an isolated SQLite database."""
    database = Database(tmp_path / "pipeline.sqlite3")
    database.initialize()
    app.state.database = database
    return TestClient(app)


def test_pipeline_runs_extract_transcribe_analyze_sort_ready(tmp_path: Path) -> None:
    """One pipeline run advances every stage and persists outputs."""
    with make_client(tmp_path) as client:
        save = client.post("/saves", headers=HEADERS, json={"url": "https://www.youtube.com/watch?v=abc123"}).json()["data"]
        service = PipelineService(
            app.state.database,
            extractor=ExtractionOrchestrator(app.state.database, video=__import__("Backend.extraction.ytdlp", fromlist=["VideoExtractor"]).VideoExtractor(StaticVideo())),
            transcriber=StaticTranscriber(),
        )
        result = service.process_save(save["id"])

        assert result["job"]["state"] == "ready"
        assert result["note"] is not None
        assert "hello world" in (result["note"]["transcript"] or "")
        assert result["save"]["needs_review"] in (True, False)


def test_pipeline_degrades_without_blocking_capture(tmp_path: Path) -> None:
    """Unknown extraction still finishes as a usable degraded save."""
    with make_client(tmp_path) as client:
        save = client.post("/saves", headers=HEADERS, json={"url": "https://example.com/missing"}).json()["data"]
        service = PipelineService(app.state.database)

        class UnknownExtractor:
            """Always unknown extractor."""

            def extract_save(self, save_id: str) -> dict:
                """Return an unknown extraction result."""
                del save_id
                return ExtractionResult(tier=1, kind="unknown").to_contract() | {"kind": "unknown", "title": None, "result": {"body": None}}

        service.extractor = UnknownExtractor()
        result = service.process_save(save["id"])

        assert result["job"]["state"] == "ready"
        assert "extracting" in result["job"]["failed"]
