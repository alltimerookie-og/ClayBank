"""Processing job orchestration."""

import asyncio
import json
import logging

from Backend.capture.service import utc_now
from Backend.errors import DomainError
from Backend.extraction.rescue import RescueExtractor
from Backend.extraction.result import ExtractionResult
from Backend.extraction.trafilatura import ArticleExtractor
from Backend.extraction.ytdlp import VideoExtractor
from Backend.store.database import Database


log = logging.getLogger(__name__)


_MAX_CACHE_ATTEMPTS = 2


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
            user_id = save["user_id"]
            platform = save["platform"]
            cache_url = url.split("#", 1)[0]
            log.info("extract: save %s platform=%s url=%s", save_id, platform, url)
            cached = self._cache_lookup(connection, user_id, cache_url)
            if cached is not None and self._cache_usable(connection, cached, user_id, cache_url, save_id):
                log.info("extract: save %s cache hit user=%s", save_id, user_id)
                result = cached
            else:
                if cached is not None:
                    log.info("extract: save %s cache stale, retrying once user=%s", save_id, user_id)
                if platform in {"youtube", "instagram", "tiktok", "facebook"}:
                    result = self._safe_video(url)
                else:
                    result = self._safe_article(url)
                if result.kind == "unknown":
                    result = self._retry_once(connection, save_id, url, platform, user_id, cache_url, result)
            log.info(
                "extract: save %s kind=%s tier=%s transcript=%s",
                save_id, result.kind, result.tier, result.transcript_available,
            )
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
            if result.kind != "unknown" and cached is None:
                self._cache_store(connection, user_id, cache_url, result, now)
                log.info("extract: save %s cache stored user=%s", save_id, user_id)
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

    def _cache_lookup(self, connection, user_id: str | None, url: str) -> ExtractionResult | None:
        """Return cached tier-1 output for the same user and URL."""
        if not user_id:
            return None
        row = connection.execute(
            "SELECT * FROM extraction_cache WHERE user_id = ? AND url = ?",
            (user_id, url),
        ).fetchone()
        if row is None:
            return None
        return ExtractionResult(
            tier=row["tier"],
            kind=row["kind"],
            title=row["title"],
            channel=row["channel"],
            body=row["body"],
            transcript_available=bool(row["transcript_available"]),
            capability_flags=json.loads(row["capability_json"] or "{}"),
            source_meta=json.loads(row["source_meta_json"] or "{}"),
        )

    def _cache_usable(self, connection, cached: ExtractionResult, user_id: str | None, url: str, save_id: str) -> bool:
        """Accept cached output only when no failed attempt came after it."""
        if cached.kind == "unknown":
            return False
        return self._prior_success(connection, user_id, url, save_id) is not False

    def _cache_attempts(self, connection, user_id: str | None, url: str, exclude_save_id: str | None = None) -> int:
        """Count completed prior extraction attempts for the same user and URL."""
        if not user_id:
            return 0
        query = """
            SELECT COUNT(*) AS total FROM jobs
            JOIN saves ON saves.id = jobs.save_id
            WHERE saves.user_id = ? AND (saves.url = ? OR saves.url LIKE ?)
            AND jobs.state NOT IN ('queued', 'extracting', 'transcribing')
            """
        params: list = [user_id, url, f"{url}#%"]
        if exclude_save_id is not None:
            query += " AND saves.id != ?"
            params.append(exclude_save_id)
        row = connection.execute(query, params).fetchone()
        return int(row["total"]) if row else 0

    def _prior_success(self, connection, user_id: str | None, url: str, exclude_save_id: str | None = None) -> bool | None:
        """Check the latest completed prior attempt: True/False, None if none."""
        if not user_id:
            return None
        query = """
            SELECT jobs.failed_json AS failed FROM jobs
            JOIN saves ON saves.id = jobs.save_id
            WHERE saves.user_id = ? AND (saves.url = ? OR saves.url LIKE ?)
            AND jobs.state NOT IN ('queued', 'extracting', 'transcribing')
            """
        params: list = [user_id, url, f"{url}#%"]
        if exclude_save_id is not None:
            query += " AND saves.id != ?"
            params.append(exclude_save_id)
        query += " ORDER BY jobs.updated_at DESC LIMIT 1"
        row = connection.execute(query, params).fetchone()
        if row is None:
            return None
        try:
            failed = json.loads(row["failed"] or "[]")
        except ValueError:
            return False
        return "extracting" not in failed

    def _retry_once(
        self,
        connection,
        save_id: str,
        url: str,
        platform: str,
        user_id: str | None,
        cache_url: str,
        result: ExtractionResult,
    ) -> ExtractionResult:
        """Retry a failed extraction once before degrading to unknown."""
        if self._cache_attempts(connection, user_id, cache_url, save_id) >= _MAX_CACHE_ATTEMPTS:
            return result
        log.info("extract: save %s retrying once user=%s", save_id, user_id)
        if platform in {"youtube", "instagram", "tiktok", "facebook"}:
            retried = self._safe_video(url)
        else:
            retried = self._safe_article(url)
        return retried if retried.kind != "unknown" else result

    def _cache_store(self, connection, user_id: str | None, url: str, result: ExtractionResult, now: str) -> None:
        """Cache successful tier-1 output under the user and URL."""
        if not user_id:
            return
        connection.execute(
            """
            INSERT INTO extraction_cache (
                user_id, url, tier, kind, title, channel, body,
                transcript_available, capability_json, source_meta_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, url) DO UPDATE SET
                tier=excluded.tier, kind=excluded.kind, title=excluded.title,
                channel=excluded.channel, body=excluded.body,
                transcript_available=excluded.transcript_available,
                capability_json=excluded.capability_json,
                source_meta_json=excluded.source_meta_json, created_at=excluded.created_at
            """,
            (
                user_id, url, result.tier, result.kind, result.title, result.channel,
                result.body, int(result.transcript_available),
                json.dumps(result.capability_flags), json.dumps(result.source_meta), now,
            ),
        )

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
