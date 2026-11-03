"""Folder organization and suggestion service."""

import hashlib
import json

from Backend.capture.service import CaptureService
from Backend.contracts.organization import FolderWrite, SuggestionAccept
from Backend.errors import DomainError
from Backend.store.database import Database
from Backend.store.identifiers import new_uuid7


RESERVED_FOLDER_NAMES = {"other", "misc", "unsorted", "inbox"}
CLUSTER_MIN_SIZE = 3


def utc_now() -> str:
    """Return the current UTC time in contract format."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


class FolderService:
    """Manage user-created folders and their member saves."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def list_folders(self, *, cursor: str | None = None) -> dict:
        """Return a cursor-shaped folder page."""
        del cursor
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT id FROM folders ORDER BY created_at LIMIT 51",
            ).fetchall()
            items = [self._get_folder(connection, row["id"]) for row in rows[:50]]
        return {"items": items, "cursor": str(rows[50]["id"]) if len(rows) > 50 else None}

    def create_folder(self, payload: FolderWrite) -> dict:
        """Create a folder from an explicit user action."""
        name = payload.name.strip()
        if not name:
            raise DomainError("validation", "Folder name is required")
        if name.lower() in RESERVED_FOLDER_NAMES:
            raise DomainError("reserved_folder_name", "This folder name is reserved")
        with self.database.transaction() as connection:
            depth = 0
            if payload.parent_id is not None:
                parent = self._require_folder(connection, str(payload.parent_id))
                if parent["archived_at"] is not None:
                    raise DomainError("validation", "Cannot create a folder under an archived folder")
                depth = self._depth(connection, str(payload.parent_id)) + 1
            if depth > 3:
                raise DomainError("folder_depth_exceeded", "Folder depth may not exceed 3")
            now = utc_now()
            folder_id = str(new_uuid7())
            connection.execute(
                """
                INSERT INTO folders (id, parent_id, name, depth, created_at, updated_at, archived_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    folder_id,
                    str(payload.parent_id) if payload.parent_id else None,
                    name,
                    depth,
                    now,
                    now,
                    payload.archived_at.isoformat().replace("+00:00", "Z") if payload.archived_at else None,
                ),
            )
            connection.execute(
                "INSERT INTO changes (entity, entity_id, op, at) VALUES ('folder', ?, 'put', ?)",
                (folder_id, now),
            )
            return self._get_folder(connection, folder_id)

    def patch_folder(self, folder_id: str, payload: FolderWrite) -> dict:
        """Rename, move, or archive one folder."""
        name = payload.name.strip()
        if not name:
            raise DomainError("validation", "Folder name is required")
        if name.lower() in RESERVED_FOLDER_NAMES:
            raise DomainError("reserved_folder_name", "This folder name is reserved")
        with self.database.transaction() as connection:
            folder = self._require_folder(connection, folder_id)
            parent_id = folder["parent_id"]
            depth = self._depth(connection, folder_id)
            if "parent_id" in payload.model_fields_set:
                parent_id = str(payload.parent_id) if payload.parent_id else None
                if parent_id == folder_id:
                    raise DomainError("validation", "A folder cannot be its own parent")
                if parent_id is not None:
                    parent = self._require_folder(connection, parent_id)
                    if parent["archived_at"] is not None:
                        raise DomainError("validation", "Cannot move a folder under an archived folder")
                    depth = self._depth(connection, parent_id) + 1
                else:
                    depth = 0
                self._require_depth(connection, folder_id, depth)
            archived_at = payload.archived_at.isoformat().replace("+00:00", "Z") if payload.archived_at else folder["archived_at"]
            now = utc_now()
            connection.execute(
                "UPDATE folders SET parent_id = ?, name = ?, depth = ?, updated_at = ?, archived_at = ? WHERE id = ?",
                (parent_id, name, depth, now, archived_at, folder_id),
            )
            connection.execute(
                "INSERT INTO changes (entity, entity_id, op, at) VALUES ('folder', ?, 'patch', ?)",
                (folder_id, now),
            )
            return self._get_folder(connection, folder_id)

    def delete_folder(self, folder_id: str) -> None:
        """Delete a folder and return member saves to the Inbox."""
        with self.database.transaction() as connection:
            self._require_folder(connection, folder_id)
            connection.execute("UPDATE saves SET folder_id = NULL WHERE folder_id = ?", (folder_id,))
            connection.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
            connection.execute(
                "INSERT INTO changes (entity, entity_id, op, at) VALUES ('folder', ?, 'delete', ?)",
                (folder_id, utc_now()),
            )

    def list_suggestions(self, capture: CaptureService) -> dict:
        """Return review saves and one outstanding cluster proposal."""
        with self.database.transaction() as connection:
            review_rows = connection.execute(
                "SELECT id FROM saves WHERE needs_review = 1 ORDER BY captured_at DESC",
            ).fetchall()
            review = [capture.get_save_bundle(row["id"])["save"] for row in review_rows]
            clusters = [
                self._suggestion_shape(row)
                for row in connection.execute(
                    "SELECT * FROM suggestions WHERE type = 'cluster' AND dismissed_at IS NULL AND accepted_at IS NULL ORDER BY created_at"
                ).fetchall()
                if not self._is_rejected(connection, self._member_ids(self._suggestion_shape(row)))
            ]
            if not clusters:
                proposal = self._cluster_proposal(connection, capture)
                if proposal is not None:
                    clusters = [proposal]
            return {"review": review, "clusters": clusters}

    def accept_suggestion(self, payload: SuggestionAccept, capture: CaptureService) -> dict | None:
        """Accept or dismiss one single or cluster suggestion.

        Returns the filed folder on accept, or None on dismissal after the
        dismissal has been committed.
        """
        if payload.type not in {"single", "cluster"}:
            raise DomainError("validation", "Suggestion type must be single or cluster")
        if not payload.path.strip():
            raise DomainError("validation", "Suggestion path is required")
        if not 0 <= payload.confidence <= 1:
            raise DomainError("validation", "Suggestion confidence must be between 0 and 1")
        if payload.type == "single" and payload.save_id is None:
            raise DomainError("validation", "Single suggestions require save_id")
        if payload.type == "cluster" and not payload.cluster:
            raise DomainError("validation", "Cluster suggestions require cluster members")
        now = utc_now()
        dismissed_at = payload.dismissed_at.isoformat().replace("+00:00", "Z") if payload.dismissed_at else None
        with self.database.transaction() as connection:
            if payload.type == "single":
                save = capture.get_save_bundle(str(payload.save_id))["save"]
                if not payload.accept:
                    self._store_suggestion(connection, payload, now, dismissed_at or now, save_id=save["id"])
                    return None
                folder = self._folder_for_path(connection, payload.path)
                connection.execute(
                    "UPDATE saves SET folder_id = ?, updated_at = ? WHERE id = ?",
                    (folder["id"], now, save["id"]),
                )
                self._store_suggestion(connection, payload, now, None, save_id=save["id"], accepted=True)
                return self._get_folder(connection, folder["id"])
            members = [str(member.save_id) for member in payload.cluster or []]
            if not payload.accept:
                self._store_suggestion(connection, payload, now, dismissed_at or now, members=members)
                return None
            for member_id in members:
                capture.get_save_bundle(member_id)
            folder = self._folder_for_path(connection, payload.path)
            for member_id in members:
                connection.execute(
                    "UPDATE saves SET folder_id = ?, updated_at = ? WHERE id = ?",
                    (folder["id"], now, member_id),
                )
            self._store_suggestion(connection, payload, now, None, members=members, accepted=True)
            return self._get_folder(connection, folder["id"])

    @staticmethod
    def _require_folder(connection, folder_id: str) -> dict:
        row = connection.execute("SELECT * FROM folders WHERE id = ?", (folder_id,)).fetchone()
        if row is None:
            raise DomainError("not_found", "Folder not found")
        return row

    @staticmethod
    def _depth(connection, folder_id: str) -> int:
        depth = 0
        current_id: str | None = folder_id
        while current_id is not None:
            row = connection.execute(
                "SELECT parent_id FROM folders WHERE id = ?",
                (current_id,),
            ).fetchone()
            if row is None:
                break
            current_id = row["parent_id"]
            if current_id is not None:
                depth += 1
        return depth

    def _require_depth(self, connection, folder_id: str, depth: int) -> None:
        if depth > 3:
            raise DomainError("folder_depth_exceeded", "Folder depth may not exceed 3")
        child_rows = connection.execute(
            "SELECT id FROM folders WHERE parent_id = ?",
            (folder_id,),
        ).fetchall()
        for child in child_rows:
            self._require_depth(connection, child["id"], depth + 1)

    @staticmethod
    def _get_folder(connection, folder_id: str) -> dict:
        row = connection.execute("SELECT * FROM folders WHERE id = ?", (folder_id,)).fetchone()
        if row is None:
            raise DomainError("not_found", "Folder not found")
        save_count = connection.execute(
            "SELECT COUNT(*) AS total FROM saves WHERE folder_id = ?",
            (folder_id,),
        ).fetchone()["total"]
        return {
            "id": row["id"],
            "parent_id": row["parent_id"],
            "name": row["name"],
            "save_count": save_count,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "archived_at": row["archived_at"],
        }

    def _suggestion_shape(self, row) -> dict:
        cluster = json.loads(row["cluster_json"]) if row["cluster_json"] else None
        return {
            "type": row["type"],
            "save_id": row["save_id"],
            "cluster": cluster,
            "path": row["path"],
            "confidence": row["confidence"],
            "dismissed_at": row["dismissed_at"],
            "accepted": row["accepted_at"] is not None,
        }

    def _cluster_proposal(self, connection, capture: CaptureService) -> dict | None:
        """Propose one cluster when enough unfiled saves remain."""
        rows = connection.execute(
            "SELECT id FROM saves WHERE folder_id IS NULL ORDER BY captured_at LIMIT 50",
        ).fetchall()
        if len(rows) < CLUSTER_MIN_SIZE:
            return None
        members = [row["id"] for row in rows[:CLUSTER_MIN_SIZE]]
        if self._is_rejected(connection, members):
            return None
        now = utc_now()
        cluster = [
            {"save_id": member_id, "title": capture.get_save_bundle(member_id)["save"].get("title")}
            for member_id in members
        ]
        suggestion_id = str(new_uuid7())
        connection.execute(
            """
            INSERT INTO suggestions (id, type, cluster_json, path, confidence, created_at)
            VALUES (?, 'cluster', ?, ?, ?, ?)
            """,
            (suggestion_id, json.dumps(cluster), "Inbox Review", 0.5, now),
        )
        return self._suggestion_shape(
            connection.execute("SELECT * FROM suggestions WHERE id = ?", (suggestion_id,)).fetchone()
        )

    @staticmethod
    def _member_ids(suggestion: dict) -> list[str]:
        """Return the member IDs for single or cluster suggestions."""
        if suggestion.get("save_id"):
            return [str(suggestion["save_id"])]
        return [str(member["save_id"]) for member in suggestion.get("cluster") or []]

    @staticmethod
    def _is_rejected(connection, members: list[str]) -> bool:
        """Check whether this exact member set was dismissed."""
        if not members:
            return False
        fingerprint = hashlib.sha256(",".join(sorted(members)).encode()).hexdigest()
        return (
            connection.execute(
                "SELECT fingerprint FROM suggestion_rejections WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
            is not None
        )

    def _store_suggestion(
        self,
        connection,
        payload: SuggestionAccept,
        now: str,
        dismissed_at: str | None,
        save_id: str | None = None,
        members: list[str] | None = None,
        accepted: bool = False,
    ) -> None:
        cluster_json = None
        if members is not None:
            cluster_json = json.dumps([{"save_id": member_id, "title": None} for member_id in members])
        connection.execute(
            """
            INSERT INTO suggestions (id, type, save_id, cluster_json, path, confidence, dismissed_at, accepted_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(new_uuid7()),
                payload.type,
                save_id,
                cluster_json,
                payload.path,
                payload.confidence,
                dismissed_at,
                now if accepted else None,
                now,
            ),
        )
        fingerprint_members = members or ([save_id] if save_id else [])
        if dismissed_at and fingerprint_members:
            fingerprint = hashlib.sha256(",".join(sorted(fingerprint_members)).encode()).hexdigest()
            connection.execute(
                "INSERT OR IGNORE INTO suggestion_rejections (fingerprint, dismissed_at) VALUES (?, ?)",
                (fingerprint, dismissed_at),
            )

    def _folder_for_path(self, connection, path: str) -> dict:
        """Resolve a slash-separated path, creating missing folders."""
        names = [part.strip() for part in path.split("/") if part.strip()]
        if not names:
            raise DomainError("validation", "Suggestion path is required")
        parent_id: str | None = None
        folder: dict | None = None
        for level, name in enumerate(names):
            if name.lower() in RESERVED_FOLDER_NAMES:
                raise DomainError("reserved_folder_name", "This folder name is reserved")
            if parent_id is None:
                row = connection.execute(
                    "SELECT * FROM folders WHERE parent_id IS NULL AND name = ?",
                    (name,),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT * FROM folders WHERE parent_id = ? AND name = ?",
                    (parent_id, name),
                ).fetchone()
            if row is None:
                if level > 3:
                    raise DomainError("folder_depth_exceeded", "Folder depth may not exceed 3")
                now = utc_now()
                folder_id = str(new_uuid7())
                connection.execute(
                    """
                    INSERT INTO folders (id, parent_id, name, depth, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (folder_id, parent_id, name, level, now, now),
                )
                folder = self._get_folder(connection, folder_id)
            else:
                folder = self._get_folder(connection, row["id"])
            parent_id = folder["id"] if folder else None
        if folder is None:
            raise DomainError("validation", "Suggestion path is required")
        return folder
