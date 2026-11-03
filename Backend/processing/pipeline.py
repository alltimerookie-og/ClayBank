"""Full save processing pipeline."""

from __future__ import annotations

import json

from Backend.asr.service import TranscriptionService
from Backend.capture.service import CaptureService, utc_now
from Backend.config import Settings, load_settings
from Backend.errors import DomainError
from Backend.extraction.result import ExtractionResult
from Backend.extraction.ytdlp import transient_media_download
from Backend.llm.provider import provider_from_settings
from Backend.processing.orchestrator import ExtractionOrchestrator
from Backend.store.database import Database


PIPELINE_STATES = ("queued", "extracting", "transcribing", "analyzing", "sorting", "ready")


class PipelineService:
    """Run extraction, transcription, analysis, sorting, and readiness."""

    def __init__(
        self,
        database: Database,
        settings: Settings | None = None,
        extractor: ExtractionOrchestrator | None = None,
        transcriber: TranscriptionService | None = None,
    ) -> None:
        self.database = database
        self.settings = settings or load_settings()
        self.extractor = extractor or ExtractionOrchestrator(database)
        self.transcriber = transcriber or TranscriptionService(settings=self.settings)
        self.capture = CaptureService(database)
        self.chat = provider_from_settings(self.settings)

    def process_save(self, save_id: str) -> dict:
        """Run one save through every pipeline stage with durable updates."""
        self._set_state(save_id, "extracting")
        extraction = self.extractor.extract_save(save_id)
        if extraction["kind"] == "unknown":
            return self._finish(save_id, degraded=True)
        self._set_state(save_id, "transcribing")
        transcript = self._transcribe(save_id, extraction)
        self._set_state(save_id, "analyzing")
        note = self._analyze(save_id, extraction, transcript)
        self._set_state(save_id, "sorting")
        self._sort(save_id, extraction, note)
        return self._finish(save_id, degraded=False)

    def _transcribe(self, save_id: str, extraction: dict) -> str | None:
        """Transcribe transient media and persist transcript text."""
        bundle = self.capture.get_save_bundle(save_id)
        url = bundle["save"]["url"]
        try:
            with transient_media_download(url) as media:
                text, _ = self.transcriber.transcribe(media.path if media else None)
        except Exception:
            text = None
        if not text and extraction["result"].get("body"):
            text = extraction["result"]["body"]
        with self.database.transaction() as connection:
            if text:
                connection.execute(
                    """
                    UPDATE notes SET transcript = ?, updated_at = ? WHERE save_id = ?
                    """,
                    (text, utc_now(), save_id),
                )
                self._mark(connection, save_id, "transcribing", failed=None)
            else:
                self._mark(connection, save_id, "transcribing", failed="transcription_failed")
        return text

    def _analyze(self, save_id: str, extraction: dict, transcript: str | None) -> dict:
        """Generate or synthesize a structured note for one save."""
        bundle = self.capture.get_save_bundle(save_id)
        save = bundle["save"]
        title = extraction.get("title") or save.get("title") or "Untitled save"
        body = extraction["result"].get("body")
        generated = self._cloud_note(save_id, title, body, transcript)
        overview = (generated or {}).get("overview") or (body or transcript or "")[:500]
        key_points = (generated or {}).get("key_points") or []
        links = (generated or {}).get("links") or []
        transcript_block = f"\n\n## Transcript\n{transcript}" if transcript else ""
        markdown = (
            "---\n"
            f"source: {save['platform']}\n"
            f"video_url: {save['url']}\n"
            "---\n"
            f"# {title}\n\n"
            f"## Overview\n{overview}\n\n"
            "## Key points\n"
            + "".join(f"- {point}\n" for point in key_points)
            + transcript_block
            + "\n"
        )
        with self.database.transaction() as connection:
            now = utc_now()
            connection.execute(
                """
                INSERT INTO notes (
                    save_id, markdown, source, channel, video_url, duration,
                    published, saved_date, folder_path, tags_json, overview,
                    key_points_json, links_json, transcript, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(save_id) DO UPDATE SET
                    markdown=excluded.markdown, source=excluded.source,
                    channel=excluded.channel, video_url=excluded.video_url,
                    duration=excluded.duration, overview=excluded.overview,
                    key_points_json=excluded.key_points_json, links_json=excluded.links_json,
                    transcript=excluded.transcript, updated_at=excluded.updated_at
                """,
                (
                    save_id,
                    markdown,
                    save["platform"],
                    save.get("title"),
                    save["url"],
                    None,
                    None,
                    None,
                    None,
                    "[]",
                    overview,
                    json.dumps(key_points),
                    json.dumps(links),
                    transcript,
                    now,
                    now,
                ),
            )
            if generated:
                self._mark(connection, save_id, "analyzing", failed=None)
            else:
                self._mark(connection, save_id, "analyzing", failed="llm_unavailable")
        return self.capture.get_save_bundle(save_id)["note"] or {}

    def _cloud_note(self, save_id: str, title: str | None, body: str | None, transcript: str | None) -> dict | None:
        """Generate structured note sections through the cloud model."""
        if self.chat is None:
            return None
        context = "\n\n".join(part for part in [title, body, transcript] if part)[:6000]
        try:
            answer = self.chat.answer(
                "Create note JSON with overview, key_points, and links.",
                context,
            )
        except DomainError:
            return None
        if not answer:
            return None
        try:
            parsed = json.loads(answer[answer.index("{") : answer.rindex("}") + 1])
        except (ValueError, AttributeError):
            return None
        if not isinstance(parsed, dict):
            return None
        return {
            "overview": parsed.get("overview"),
            "key_points": parsed.get("key_points") or [],
            "links": parsed.get("links") or [],
        }

    def _sort(self, save_id: str, extraction: dict, note: dict) -> dict:
        """Assign a folder suggestion and mark review state."""
        del extraction, note
        bundle = self.capture.get_save_bundle(save_id)
        save = bundle["save"]
        confidence = 0.5 if save.get("folder_id") is None else 1.0
        path = "Inbox Review"
        suggested = {"path": path, "confidence": confidence}
        needs_review = confidence < self.settings.suggestion_threshold
        with self.database.transaction() as connection:
            now = utc_now()
            connection.execute(
                """
                UPDATE saves
                SET suggested_folder_path = ?, suggested_folder_confidence = ?,
                    needs_review = ?, updated_at = ?
                WHERE id = ?
                """,
                (path, confidence, int(needs_review), now, save_id),
            )
            self._mark(connection, save_id, "sorting", failed=None)
        return suggested

    def _finish(self, save_id: str, *, degraded: bool) -> dict:
        """Mark one save ready while preserving degraded-state visibility."""
        with self.database.transaction() as connection:
            now = utc_now()
            row = connection.execute("SELECT * FROM jobs WHERE save_id = ?", (save_id,)).fetchone()
            if row is None:
                raise DomainError("not_found", "Processing job not found")
            failed = json.loads(row["failed_json"])
            if degraded and "extracting" not in failed:
                failed.append("extracting")
            connection.execute(
                "UPDATE jobs SET state = ?, failed_json = ?, updated_at = ? WHERE save_id = ?",
                ("ready", json.dumps(failed), now, save_id),
            )
            connection.execute(
                "INSERT INTO changes (entity, entity_id, op, at) VALUES ('job', ?, 'put', ?)",
                (save_id, now),
            )
        return self.capture.get_save_bundle(save_id)

    def _set_state(self, save_id: str, state: str) -> None:
        """Move one job to the next pipeline stage."""
        if state not in PIPELINE_STATES:
            raise DomainError("validation", "Invalid pipeline state")
        with self.database.transaction() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE save_id = ?", (save_id,)).fetchone()
            if row is None:
                raise DomainError("not_found", "Processing job not found")
            connection.execute(
                "UPDATE jobs SET state = ?, updated_at = ? WHERE save_id = ?",
                (state, utc_now(), save_id),
            )

    @staticmethod
    def _mark(connection, save_id: str, stage: str, *, failed: str | None) -> None:
        """Record stage success or failure without losing other flags."""
        row = connection.execute("SELECT skipped_json, failed_json FROM jobs WHERE save_id = ?", (save_id,)).fetchone()
        skipped = json.loads(row["skipped_json"]) if row else []
        failed_flags = json.loads(row["failed_json"]) if row else []
        now = utc_now()
        if failed:
            if failed not in failed_flags:
                failed_flags.append(failed)
            connection.execute(
                "UPDATE jobs SET failed_json = ?, error = ?, updated_at = ? WHERE save_id = ?",
                (json.dumps(failed_flags), failed, now, save_id),
            )
        else:
            connection.execute(
                "UPDATE jobs SET skipped_json = ?, updated_at = ? WHERE save_id = ?",
                (json.dumps(skipped), now, save_id),
            )
        connection.execute(
            "INSERT INTO changes (entity, entity_id, op, at) VALUES ('job', ?, 'put', ?)",
            (save_id, now),
        )
