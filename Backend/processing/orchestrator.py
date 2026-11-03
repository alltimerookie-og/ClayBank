"""Processing job orchestration."""

import asyncio
import json

from Backend.capture.service import utc_now
from Backend.errors import DomainError
from Backend.extraction.rescue import RescueExtractor
from Backend.extraction.result import ExtractionResult
from Backend.extraction.trafilatura import ArticleExtractor
from Backend.extraction.ytdlp import VideoExtractor
from Backend.store.database import Database


class ExtractionOrchestrator:
    """Run tier-1 extraction and record the extraction stage outcome."""

    def __init__(
        self,
        database: Database,
        video: VideoExtractor | None = None,
        article: ArticleExtractor | None = None,
        rescue: RescueExtractor | None = None,
        max_workers: int = 5,
    ) -> None:
        self.database = database
        self.video = video or VideoExtractor()
        self.article = article or ArticleExtractor()
        self.rescue = rescue or RescueExtractor()
        self.max_workers = max(1, max_workers)

    def extract_save(self, save_id: str) -> dict:
        """Extract one save and persist the tier-1 result."""
        with self.database.transaction() as connection:
            save = connection.execute("SELECT * FROM saves WHERE id = ?", (save_id,)).fetchone()
            if save is None:
                raise DomainError("not_found", "Save not found")
            job = connection.execute("SELECT * FROM jobs WHERE save_id = ?", (save_id,)).fetchone()
            if job is None:
                raise DomainError("not_found", "Processing job not found")
            url = save["url"]
            platform = save["platform"]
            if platform in {"youtube", "instagram", "tiktok", "facebook"}:
                result = self._safe_video(url)
            else:
                result = self._safe_article(url)
            now = utc_now()
            connection.execute(
                """
                INSERT INTO extraction_results (
                    save_id, tier, kind, title, channel, body, transcript_available,
                    capability_json, source_meta_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(save_id) DO UPDATE SET
                    tier=excluded.tier, kind=excluded.kind, title=excluded.title,
                    channel=excluded.channel, body=excluded.body,
                    transcript_available=excluded.transcript_available,
                    capability_json=excluded.capability_json,
                    source_meta_json=excluded.source_meta_json, created_at=excluded.created_at
                """,
                (
                    save_id,
                    result.tier,
                    result.kind,
                    result.title,
                    result.channel,
                    result.body,
                    int(result.transcript_available),
                    json.dumps(result.capability_flags),
                    json.dumps(result.source_meta),
                    now,
                ),
            )
            kind = result.kind
            title = result.title
            failed = json.loads(job["failed_json"])
            skipped = json.loads(job["skipped_json"])
            error: str | None = None
            next_state = "transcribing"
            if result.kind == "unknown":
                rescue = self.rescue.rescue(url, kind)
                tier = rescue.tier
                connection.execute(
                    "UPDATE jobs SET state = ?, tier = ?, failed_json = ?, error = ?, updated_at = ? WHERE save_id = ?",
                    ("analyzing", tier, json.dumps([*failed, "extracting"]), "extraction_failed", now, save_id),
                )
                next_state = "analyzing"
            else:
                connection.execute(
                    "UPDATE jobs SET state = ?, skipped_json = ?, updated_at = ? WHERE save_id = ?",
                    (next_state, json.dumps(skipped), now, save_id),
                )
            connection.execute(
                """
                UPDATE saves
                SET kind = ?, title = COALESCE(?, title), has_audio = ?, has_timeline = ?,
                    has_images = ?, duration = COALESCE(?, duration), updated_at = ?
                WHERE id = ?
                """,
                (
                    kind,
                    title,
                    int(result.capability_flags.get("has_audio", False)),
                    int(result.capability_flags.get("has_timeline", False)),
                    int(result.capability_flags.get("has_images", False)),
                    result.duration,
                    now,
                    save_id,
                ),
            )
            connection.execute(
                "INSERT INTO changes (entity, entity_id, op, at) VALUES ('save', ?, 'patch', ?)",
                (save_id, now),
            )
            connection.execute(
                "INSERT INTO changes (entity, entity_id, op, at) VALUES ('job', ?, 'put', ?)",
                (save_id, now),
            )
            return {
                "save_id": save_id,
                "state": next_state if result.kind != "unknown" else "analyzing",
                "tier": 2 if result.kind == "unknown" else 1,
                "kind": kind,
                "title": title,
                "transcript_available": result.transcript_available,
                "error": error,
                "result": result.to_contract(),
            }

    def extract_many(self, save_ids: list[str]) -> list[dict]:
        """Extract multiple saves in parallel with bounded concurrency."""
        return asyncio.run(self._extract_many_async(save_ids))

    async def _extract_many_async(self, save_ids: list[str]) -> list[dict]:
        """Run extraction across saves with isolated database connections."""
        semaphore = asyncio.Semaphore(self.max_workers)

        async def _extract_one(save_id: str) -> dict:
            async with semaphore:
                return await asyncio.to_thread(self._extract_with_fresh_database, save_id)

        return list(await asyncio.gather(*(_extract_one(save_id) for save_id in save_ids)))

    def _extract_with_fresh_database(self, save_id: str) -> dict:
        """Extract one save without sharing the caller's SQLite connection."""
        database = Database(self.database.path)
        database.initialize()
        try:
            orchestrator = ExtractionOrchestrator(
                database,
                video=self.video,
                article=self.article,
                rescue=self.rescue,
                max_workers=1,
            )
            return orchestrator.extract_save(save_id)
        finally:
            database.close()

    def _safe_video(self, url: str) -> ExtractionResult:
        """Run video extraction and degrade cleanly on provider failure."""
        try:
            return self.video.extract(url)
        except Exception:
            return ExtractionResult(tier=1, kind="unknown")

    def _safe_article(self, url: str) -> ExtractionResult:
        """Run article extraction and degrade cleanly on provider failure."""
        try:
            return self.article.extract(url)
        except Exception:
            return ExtractionResult(tier=1, kind="unknown")
