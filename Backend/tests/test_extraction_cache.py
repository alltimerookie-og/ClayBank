"""Focused tests for intake cache check with success verification and retry."""

from pathlib import Path

from Backend.processing.orchestrator import ExtractionOrchestrator
from Backend.extraction.result import ExtractionResult
from Backend.store.database import Database


class ScriptedVideo:
    """Video provider replaying queued results and counting invocations."""

    def __init__(self, results: list[ExtractionResult]) -> None:
        self.results = list(results)
        self.calls = 0

    def extract(self, url: str):
        """Return the next queued result and count the call."""
        self.calls += 1
        if len(self.results) > 1:
            return self.results.pop(0)
        return self.results[0]


def make_save(db: Database, url: str) -> str:
    """Insert one save with a job and return its id."""
    import uuid

    save_id = str(uuid.uuid4())
    with db.transaction() as connection:
        connection.execute(
            "INSERT INTO saves (id, raw_url, url, platform, source_app, user_context, kind, captured_by_device, user_id, captured_at, created_at, updated_at)"
            " VALUES (?, ?, ?, 'youtube', 'test', '', 'unknown', 'd1', 'dev-user', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')",
            (save_id, url, url),
        )
        connection.execute(
            "INSERT INTO jobs (save_id, state, tier, created_at, updated_at) VALUES (?, 'queued', 1, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')",
            (save_id,),
        )
    return save_id


def test_same_user_same_link_reuses_cache(tmp_path: Path) -> None:
    """Second save of the same URL skips the provider."""
    db = Database(tmp_path / "cache.sqlite3")
    db.initialize()
    result = ExtractionResult(tier=1, kind="video", title="Cached", transcript_available=True)
    video = ScriptedVideo([result])
    service = ExtractionOrchestrator(db, video=video)
    first = make_save(db, "https://example.com/v")
    second = make_save(db, "https://example.com/v#claybank-copy=second")

    service.extract_save(first)
    service.extract_save(second)

    assert video.calls == 1


def test_unknown_results_are_not_cached(tmp_path: Path) -> None:
    """Degraded extractions always retry the provider."""
    db = Database(tmp_path / "cache2.sqlite3")
    db.initialize()
    video = ScriptedVideo([ExtractionResult(tier=1, kind="unknown")])
    service = ExtractionOrchestrator(db, video=video)
    first = make_save(db, "https://example.com/u")
    second = make_save(db, "https://example.com/u#claybank-copy=second")

    service.extract_save(first)
    service.extract_save(second)

    assert video.calls == 4


def test_cache_hit_requires_prior_success(tmp_path: Path) -> None:
    """A failed prior attempt forces a fresh extraction, not a blind reuse."""
    db = Database(tmp_path / "cache3.sqlite3")
    db.initialize()
    cached = ExtractionResult(tier=1, kind="video", title="Cached", transcript_available=True)
    with db.transaction() as connection:
        connection.execute(
            "INSERT INTO extraction_cache (user_id, url, tier, kind, title, body, transcript_available, capability_json, source_meta_json, created_at)"
            " VALUES ('dev-user', 'https://example.com/s', 1, 'video', 'Cached', '', 1, '{}', '{}', '2026-01-01T00:00:00Z')"
        )
    failed_id = make_save(db, "https://example.com/s")
    service = ExtractionOrchestrator(db, video=ScriptedVideo([cached]))
    service.extract_save(failed_id)
    with db.transaction() as connection:
        connection.execute(
            "UPDATE jobs SET state = 'ready', failed_json = ?, error = ? WHERE save_id = ?",
            ('["extracting"]', "extraction_failed", failed_id),
        )
    fresh = make_save(db, "https://example.com/s#claybank-copy=next")
    video = ScriptedVideo([cached])
    service = ExtractionOrchestrator(db, video=video)

    outcome = service.extract_save(fresh)

    assert video.calls == 1
    assert outcome["kind"] == "video"


def test_failed_extraction_retries_once(tmp_path: Path) -> None:
    """First failure retries the provider once before degrading."""
    db = Database(tmp_path / "cache4.sqlite3")
    db.initialize()
    failed = ExtractionResult(tier=1, kind="unknown")
    recovered = ExtractionResult(tier=1, kind="video", title="Recovered", transcript_available=True)
    video = ScriptedVideo([failed, recovered])
    service = ExtractionOrchestrator(db, video=video)
    save_id = make_save(db, "https://example.com/r")

    outcome = service.extract_save(save_id)

    assert video.calls == 2
    assert outcome["kind"] == "video"
