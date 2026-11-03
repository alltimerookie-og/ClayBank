"""Durable save capture service."""

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from uuid import UUID

from Backend.capture.canonicalize import canonicalize_url, platform_for_url
from Backend.contracts.saves import NotePut, SaveCapture, SavePatch, TagsPut
from Backend.errors import DomainError
from Backend.store.database import Database
from Backend.store.identifiers import new_uuid7


def utc_now() -> str:
    """Return the current UTC time in contract format."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


class CaptureService:
    """Persist capture records before any downstream pipeline work."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def capture(
        self,
        payload: SaveCapture,
        *,
        user_id: str,
        device_id: str,
        idempotency_key: str | None,
    ) -> tuple[dict, bool]:
        """Create or safely replay one save capture."""
        raw_url = str(payload.url)
        canonical_url = canonicalize_url(raw_url)
        payload_hash = hashlib.sha256(
            json.dumps(payload.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest()

        with self.database.transaction() as connection:
            if idempotency_key:
                replay = connection.execute(
                    """
                    SELECT payload_hash, resulting_id
                    FROM idempotency_keys
                    WHERE user_id = ? AND key = ?
                    """,
                    (user_id, idempotency_key),
                ).fetchone()
                if replay:
                    if replay["payload_hash"] != payload_hash:
                        raise DomainError("conflict", "Idempotency-Key was reused with a different body")
                    existing = self._get_save(connection, replay["resulting_id"])
                    if existing is None:
                        raise DomainError("not_found", "Idempotency result no longer exists")
                    return existing, True

            existing = connection.execute(
                "SELECT id FROM saves WHERE url = ?",
                (canonical_url,),
            ).fetchone()
            if existing and not payload.force:
                raise DomainError(
                    "already_saved",
                    "This link has already been saved",
                    {"existing_id": existing["id"]},
                )

            now = utc_now()
            save_id = str(new_uuid7())
            stored_url = (
                f"{canonical_url}#claybank-copy={save_id}"
                if existing and payload.force
                else canonical_url
            )
            source_app = payload.source_app.strip().lower() or "unknown"
            connection.execute(
                """
                INSERT INTO saves (
                    id, raw_url, url, platform, source_app, user_context, kind,
                    folder_id, captured_by_device, user_id, captured_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'unknown', ?, ?, ?, ?, ?, ?)
                """,
                (
                    save_id,
                    raw_url,
                    stored_url,
                    platform_for_url(stored_url),
                    source_app,
                    payload.user_context,
                    str(payload.suggested_folder_id) if payload.suggested_folder_id else None,
                    device_id,
                    user_id,
                    now,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO jobs
                    (save_id, state, tier, created_at, updated_at)
                VALUES (?, 'queued', 1, ?, ?)
                """,
                (save_id, now, now),
            )
            if idempotency_key:
                connection.execute(
                    """
                    INSERT INTO idempotency_keys
                        (key, user_id, op, payload_hash, resulting_id, created_at, expires_at)
                    VALUES (?, ?, 'save_create', ?, ?, ?, ?)
                    """,
                    (idempotency_key, user_id, payload_hash, save_id, now, now),
                )
            result = self._get_save(connection, save_id)
            if result is None:
                raise DomainError("not_found", "The captured save could not be read")
            connection.execute(
                "INSERT INTO changes (entity, entity_id, op, at) VALUES ('save', ?, 'put', ?)",
                (save_id, now),
            )
            connection.execute(
                "INSERT INTO changes (entity, entity_id, op, at) VALUES ('job', ?, 'put', ?)",
                (save_id, now),
            )
            return result, False

    def list_saves(
        self,
        *,
        folder_id: str | None = None,
        inbox: bool = False,
        needs_review: bool | None = None,
        kind: str | None = None,
        cursor: str | None = None,
    ) -> dict:
        """Return a cursor-paginated save page."""
        del cursor
        conditions: list[str] = []
        values: list[object] = []
        if inbox:
            conditions.append("folder_id IS NULL")
        elif folder_id is not None:
            conditions.append("folder_id = ?")
            values.append(folder_id)
        if needs_review is not None:
            conditions.append("needs_review = ?")
            values.append(int(needs_review))
        if kind is not None:
            conditions.append("kind = ?")
            values.append(kind)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.database.transaction() as connection:
            rows = connection.execute(
                f"SELECT id FROM saves {where} ORDER BY captured_at DESC LIMIT 51",
                values,
            ).fetchall()
            items = [
                self._get_save(connection, row["id"])
                for row in rows[:50]
            ]
        return {"items": items, "cursor": str(rows[50]["id"]) if len(rows) > 50 else None}

    def get_save_bundle(self, save_id: str) -> dict:
        """Return a save, note, and processing job."""
        with self.database.transaction() as connection:
            save = self._get_save(connection, save_id)
            if save is None:
                raise DomainError("not_found", "Save not found")
            return {
                "save": save,
                "note": self._get_note(connection, save_id),
                "job": self._get_job(connection, save_id),
            }

    def patch_save(self, save_id: str, payload: SavePatch) -> dict:
        """Update mutable save fields after a stale-write check."""
        with self.database.transaction() as connection:
            row = self._require_save(connection, save_id)
            self._check_updated_at(row["updated_at"], payload.updated_at)
            updates: list[str] = []
            values: list[object] = []
            if payload.folder_id is not None or "folder_id" in payload.model_fields_set:
                updates.append("folder_id = ?")
                values.append(str(payload.folder_id) if payload.folder_id else None)
            if payload.tag_ids is not None:
                self._replace_tags(connection, save_id, payload.tag_ids)
            if payload.user_context is not None:
                updates.append("user_context = ?")
                values.append(payload.user_context)
            now = utc_now()
            updates.append("updated_at = ?")
            values.extend([now, save_id])
            connection.execute(f"UPDATE saves SET {', '.join(updates)} WHERE id = ?", values)
            connection.execute(
                "INSERT INTO changes (entity, entity_id, op, at) VALUES ('save', ?, 'patch', ?)",
                (save_id, now),
            )
            result = self._get_save(connection, save_id)
            if result is None:
                raise DomainError("not_found", "Save not found")
            return result

    def delete_save(self, save_id: str) -> None:
        """Delete a save and all cascade-owned records."""
        with self.database.transaction() as connection:
            self._require_save(connection, save_id)
            connection.execute("DELETE FROM saves WHERE id = ?", (save_id,))
            connection.execute(
                "INSERT INTO changes (entity, entity_id, op, at) VALUES ('save', ?, 'delete', ?)",
                (save_id, utc_now()),
            )

    def put_note(self, save_id: str, payload: NotePut) -> dict:
        """Replace a note and rebuild its parsed search fields."""
        with self.database.transaction() as connection:
            row = self._require_save(connection, save_id)
            self._check_updated_at(row["updated_at"], payload.updated_at)
            now = utc_now()
            parsed = _parse_frontmatter(payload.markdown)
            connection.execute(
                """
                INSERT INTO notes (
                    save_id, markdown, source, channel, video_url, duration,
                    published, saved_date, folder_path, tags_json, transcript, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(save_id) DO UPDATE SET
                    markdown=excluded.markdown, source=excluded.source,
                    channel=excluded.channel, video_url=excluded.video_url,
                    duration=excluded.duration, published=excluded.published,
                    saved_date=excluded.saved_date, folder_path=excluded.folder_path,
                    tags_json=excluded.tags_json, transcript=excluded.transcript,
                    updated_at=excluded.updated_at
                """,
                (
                    save_id,
                    payload.markdown,
                    parsed.get("source"),
                    parsed.get("channel"),
                    parsed.get("video_url"),
                    parsed.get("duration"),
                    parsed.get("published"),
                    parsed.get("saved"),
                    parsed.get("folder"),
                    json.dumps(parsed.get("tags", [])),
                    _extract_transcript(payload.markdown),
                    row["created_at"],
                    now,
                ),
            )
            connection.execute(
                "UPDATE saves SET updated_at = ? WHERE id = ?",
                (now, save_id),
            )
            connection.execute(
                "INSERT INTO changes (entity, entity_id, op, at) VALUES ('note', ?, 'put', ?)",
                (save_id, now),
            )
            note = self._get_note(connection, save_id)
            try:
                from Backend.store.vectors import VectorIndex

                passage = " ".join(
                    part
                    for part in [
                        note.get("overview") if note else None,
                        " ".join(note.get("key_points") or []) if note else "",
                        note.get("transcript") if note else None,
                        note.get("markdown") if note else "",
                    ]
                    if part
                )
                if passage.strip():
                    VectorIndex(self.database).index_note(save_id, passage)
            except Exception:
                pass
            return note

    def reprocess(self, save_id: str, from_stage: str | None) -> dict:
        """Requeue processing from a valid pipeline stage."""
        with self.database.transaction() as connection:
            self._require_save(connection, save_id)
            now = utc_now()
            connection.execute(
                """
                INSERT INTO jobs (save_id, state, tier, created_at, updated_at)
                VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(save_id) DO UPDATE SET
                    state=excluded.state, error=NULL, skipped_json='[]',
                    failed_json='[]', updated_at=excluded.updated_at
                """,
                (save_id, from_stage or "extracting", now, now),
            )
            connection.execute(
                "INSERT INTO changes (entity, entity_id, op, at) VALUES ('job', ?, 'put', ?)",
                (save_id, now),
            )
            return self._get_job(connection, save_id)

    @staticmethod
    def _require_save(connection, save_id: str):
        row = connection.execute("SELECT * FROM saves WHERE id = ?", (save_id,)).fetchone()
        if row is None:
            raise DomainError("not_found", "Save not found")
        return row

    def replace_save_tags(self, save_id: str, payload: TagsPut) -> dict:
        """Replace a save's complete flat tag set."""
        with self.database.transaction() as connection:
            row = self._require_save(connection, save_id)
            self._check_updated_at(row["updated_at"], payload.updated_at)
            connection.execute("DELETE FROM save_tags WHERE save_id = ?", (save_id,))
            try:
                for tag_id in payload.tag_ids:
                    connection.execute(
                        "INSERT INTO save_tags (save_id, tag_id) VALUES (?, ?)",
                        (save_id, str(tag_id)),
                    )
            except sqlite3.IntegrityError as exc:
                raise DomainError("not_found", "One or more tags were not found") from exc
            now = utc_now()
            connection.execute("UPDATE saves SET updated_at = ? WHERE id = ?", (now, save_id))
            connection.execute(
                "INSERT INTO changes (entity, entity_id, op, at) VALUES ('save', ?, 'patch', ?)",
                (save_id, now),
            )
            result = self._get_save(connection, save_id)
            if result is None:
                raise DomainError("not_found", "Save not found")
            return result

    @staticmethod
    def _check_updated_at(current: str, supplied: datetime | None) -> None:
        if supplied is not None and supplied.isoformat().replace("+00:00", "Z") != current:
            raise DomainError("conflict", "Stale save write", {"expected_updated_at": current})

    @staticmethod
    def _replace_tags(connection, save_id: str, tag_ids: list[UUID]) -> None:
        connection.execute("DELETE FROM save_tags WHERE save_id = ?", (save_id,))
        for tag_id in tag_ids:
            tag_row = connection.execute(
                "SELECT id FROM tags WHERE id = ?",
                (str(tag_id),),
            ).fetchone()
            if tag_row is None:
                raise DomainError("not_found", f"Tag {tag_id} not found")
            connection.execute(
                "INSERT INTO save_tags (save_id, tag_id) VALUES (?, ?)",
                (save_id, str(tag_id)),
            )

    @staticmethod
    def _get_note(connection, save_id: str) -> dict | None:
        row = connection.execute("SELECT * FROM notes WHERE save_id = ?", (save_id,)).fetchone()
        if row is None:
            return None
        frontmatter = {
            key: row[column]
            for key, column in (
                ("source", "source"),
                ("channel", "channel"),
                ("video_url", "video_url"),
                ("duration", "duration"),
                ("published", "published"),
                ("saved", "saved_date"),
                ("folder", "folder_path"),
            )
            if row[column] is not None
        }
        frontmatter["tags"] = json.loads(row["tags_json"])
        return {
            "save_id": row["save_id"],
            "markdown": row["markdown"],
            "frontmatter": frontmatter,
            "overview": row["overview"],
            "key_points": json.loads(row["key_points_json"]) if row["key_points_json"] else None,
            "links": json.loads(row["links_json"]) if row["links_json"] else None,
            "transcript": row["transcript"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _get_job(connection, save_id: str) -> dict | None:
        row = connection.execute("SELECT * FROM jobs WHERE save_id = ?", (save_id,)).fetchone()
        if row is None:
            return None
        return {
            "save_id": row["save_id"],
            "state": row["state"],
            "tier": row["tier"],
            "skipped": json.loads(row["skipped_json"]),
            "failed": json.loads(row["failed_json"]),
            "error": row["error"],
            "agent_trace": json.loads(row["agent_trace"]) if row["agent_trace"] else None,
            "timing": json.loads(row["timing_json"]) if row["timing_json"] else {},
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _get_save(connection, save_id: str) -> dict | None:
        """Read a save and map SQLite columns to the wire shape."""
        row = connection.execute(
            "SELECT * FROM saves WHERE id = ?",
            (save_id,),
        ).fetchone()
        if row is None:
            return None
        suggested_folder = None
        if row["suggested_folder_path"] is not None:
            suggested_folder = {
                "path": row["suggested_folder_path"],
                "confidence": row["suggested_folder_confidence"],
            }
        return {
            "id": row["id"],
            "url": row["url"],
            "raw_url": row["raw_url"],
            "platform": row["platform"],
            "source_app": row["source_app"],
            "user_context": row["user_context"],
            "kind": row["kind"],
            "has_audio": bool(row["has_audio"]),
            "has_timeline": bool(row["has_timeline"]),
            "has_images": bool(row["has_images"]),
            "duration": row["duration"],
            "title": row["title"],
            "needs_review": bool(row["needs_review"]),
            "folder_id": row["folder_id"],
            "suggested_folder": suggested_folder,
            "captured_by_device": row["captured_by_device"],
            "captured_at": row["captured_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


def _parse_frontmatter(markdown: str) -> dict:
    """Parse the stable scalar frontmatter fields used by the note index."""
    if not markdown.startswith("---"):
        return {}
    end = markdown.find("\n---", 3)
    if end == -1:
        return {}
    values: dict[str, object] = {}
    for line in markdown[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip("\"'")
        if key.strip() == "tags":
            values["tags"] = [tag.strip() for tag in value.strip("[]").split(",") if tag.strip()]
        elif key.strip() == "duration":
            values["duration"] = int(value) if value.isdigit() else None
        else:
            values[key.strip()] = value or None
    return values


def _extract_transcript(markdown: str) -> str | None:
    """Extract timestamped quote lines from Markdown for the FTS transcript field."""
    lines = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            text = stripped[1:].strip()
            if text:
                lines.append(text)
    return "\n".join(lines) if lines else None
