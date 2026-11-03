"""Server-authoritative synchronization service."""

import hashlib
import json

from Backend.capture.service import CaptureService, utc_now
from Backend.contracts.organization import FolderWrite, SuggestionAccept
from Backend.contracts.saves import NotePut, SaveCapture, SavePatch, TagsPut
from Backend.contracts.search import AskRequest
from Backend.contracts.sync import SyncOperation, SyncPush
from Backend.errors import DomainError
from Backend.organization.service import FolderService
from Backend.search.service import SearchService
from Backend.store.database import Database


SYNC_OPS = {
    "save_create",
    "save_patch",
    "note_put",
    "folder_create",
    "folder_patch",
    "tags_put",
    "suggestion_accept",
}


class SyncService:
    """Pull replica deltas and replay queued offline writes."""

    def __init__(self, database: Database) -> None:
        self.database = database
        self.capture = CaptureService(database)
        self.folders = FolderService(database)
        self.search = SearchService(database)

    def pull(self, since: str) -> dict:
        """Return every changed record after a monotonic cursor."""
        try:
            cursor = int(since)
        except ValueError as exc:
            raise DomainError("validation", "Sync cursor must be an integer") from exc
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT id, entity, entity_id, op FROM changes WHERE id > ? ORDER BY id LIMIT 200",
                (cursor,),
            ).fetchall()
            save_ids: set[str] = set()
            note_ids: set[str] = set()
            folder_ids: set[str] = set()
            job_ids: set[str] = set()
            deleted: list[str] = []
            max_cursor = cursor
            for row in rows:
                max_cursor = max(max_cursor, row["id"])
                if row["op"] == "delete":
                    deleted.append(row["entity_id"])
                    continue
                if row["entity"] == "save":
                    save_ids.add(row["entity_id"])
                elif row["entity"] == "note":
                    note_ids.add(row["entity_id"])
                elif row["entity"] in {"folder", "folder_rename"}:
                    folder_ids.add(row["entity_id"])
                elif row["entity"] == "job":
                    job_ids.add(row["entity_id"])
            saves = []
            for save_id in sorted(save_ids):
                try:
                    saves.append(self.capture.get_save_bundle(save_id)["save"])
                except DomainError:
                    continue
            notes = []
            for save_id in sorted(note_ids | save_ids):
                try:
                    bundle = self.capture.get_save_bundle(save_id)
                except DomainError:
                    continue
                if bundle["note"] is not None:
                    notes.append(bundle["note"])
            folders = []
            for folder_id in sorted(folder_ids):
                try:
                    folders.append(self.folders._get_folder(connection, folder_id))
                except DomainError:
                    continue
            jobs = []
            for save_id in sorted(job_ids | save_ids):
                try:
                    bundle = self.capture.get_save_bundle(save_id)
                except DomainError:
                    continue
                if bundle["job"] is not None:
                    job = dict(bundle["job"])
                    job.pop("agent_trace", None)
                    jobs.append(job)
            return {
                "saves": saves,
                "notes": notes,
                "folders": folders,
                "jobs": jobs,
                "deleted": sorted(set(deleted)),
                "cursor": str(max_cursor),
            }

    def push(self, payload: SyncPush, *, user_id: str) -> dict:
        """Replay queued operations in order with per-operation results."""
        results = []
        for operation in payload.ops:
            try:
                result_id = self._replay(operation, user_id=user_id)
                results.append({"idempotency_key": operation.idempotency_key, "ok": True, "result_id": result_id})
            except DomainError as exc:
                results.append(
                    {
                        "idempotency_key": operation.idempotency_key,
                        "ok": False,
                        "error": {"code": exc.code, "message": exc.message, "detail": exc.detail},
                    }
                )
        return {"results": results}

    def _replay(self, operation: SyncOperation, *, user_id: str) -> str | None:
        """Replay one queued operation with idempotency protection."""
        if operation.op not in SYNC_OPS:
            raise DomainError("validation", f"Unsupported sync operation: {operation.op}")
        payload_hash = hashlib.sha256(
            json.dumps(operation.payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        with self.database.transaction() as connection:
            replay = connection.execute(
                "SELECT payload_hash, resulting_id FROM idempotency_keys WHERE user_id = ? AND key = ?",
                (user_id, operation.idempotency_key),
            ).fetchone()
            if replay:
                if replay["payload_hash"] != payload_hash:
                    raise DomainError("conflict", "Idempotency key was reused with a different body")
                return replay["resulting_id"]
        if operation.op == "save_create":
            model = SaveCapture.model_validate(operation.payload)
            result, _ = self.capture.capture(model, user_id=user_id, device_id="sync", idempotency_key=None)
            self._remember(operation, user_id, payload_hash, result["id"])
            return result["id"]
        if operation.op == "save_patch":
            save_id = str(operation.payload.pop("save_id", ""))
            model = SavePatch.model_validate(operation.payload)
            result = self.capture.patch_save(save_id, model)
            self._remember(operation, user_id, payload_hash, result["id"])
            return result["id"]
        if operation.op == "note_put":
            save_id = str(operation.payload.pop("save_id", ""))
            model = NotePut.model_validate(operation.payload)
            result = self.capture.put_note(save_id, model)
            self._remember(operation, user_id, payload_hash, result["save_id"])
            return result["save_id"]
        if operation.op == "folder_create":
            model = FolderWrite.model_validate(operation.payload)
            result = self.folders.create_folder(model)
            self._remember(operation, user_id, payload_hash, result["id"])
            return result["id"]
        if operation.op == "folder_patch":
            folder_id = str(operation.payload.pop("folder_id", ""))
            model = FolderWrite.model_validate(operation.payload)
            result = self.folders.patch_folder(folder_id, model)
            self._remember(operation, user_id, payload_hash, result["id"])
            return result["id"]
        if operation.op == "tags_put":
            save_id = str(operation.payload.pop("save_id", ""))
            model = TagsPut.model_validate(operation.payload)
            result = self.capture.replace_save_tags(save_id, model)
            self._remember(operation, user_id, payload_hash, result["id"])
            return result["id"]
        if operation.op == "suggestion_accept":
            model = SuggestionAccept.model_validate(operation.payload)
            folder = self.folders.accept_suggestion(model, self.capture)
            result_id = folder["id"] if folder else None
            self._remember(operation, user_id, payload_hash, result_id)
            return result_id
        raise DomainError("validation", f"Unsupported sync operation: {operation.op}")

    def _remember(self, operation: SyncOperation, user_id: str, payload_hash: str, result_id: str | None) -> None:
        """Record an idempotent replay result."""
        assert self.database.connection is not None
        now = utc_now()
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO idempotency_keys (key, user_id, op, payload_hash, resulting_id, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, key) DO NOTHING
                """,
                (operation.idempotency_key, user_id, operation.op, payload_hash, result_id, now, now),
            )

    def record(self, entity: str, entity_id: str, op: str) -> None:
        """Append one server change-log entry."""
        assert self.database.connection is not None
        with self.database.transaction() as connection:
            connection.execute(
                "INSERT INTO changes (entity, entity_id, op, at) VALUES (?, ?, ?, ?)",
                (entity, entity_id, op, utc_now()),
            )
