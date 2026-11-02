"""Frontend synchronization coordinator and client payload hygiene manager.

Bridges the Settings UI and conflict surfaces with sync operations, manages
in-memory settings defaults adhering to Docs/db/0003_device.sql, validates outbound
push payloads against Docs/api/schemas/sync-push.json, and enforces exclusion of
agent_trace diagnostics per ADR 0002.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable
import uuid

CONTRACT_VERSION = "0"

ALLOWED_OPS = {
    "save_create",
    "save_patch",
    "note_put",
    "folder_create",
    "folder_patch",
    "tags_put",
    "suggestion_accept",
}

DEFAULT_SETTINGS: dict[str, Any] = {
    "chat_model": "cloud",
    "local_model_id": "minicpm5-2b",
    "auto_sort": True,
    "weekly_digest": True,
    "wifi_only_processing": False,
    "quick_save_notification": True,
}


def sanitize_push_payload(op: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Sanitize operation payload ensuring forbidden diagnostic fields are stripped.

    ADR 0002 / Rules.md §5: agent_trace and internal pipeline diagnostics must
    never enter client sync push payloads.
    """
    if op not in ALLOWED_OPS:
        raise ValueError(f"Unknown or unsupported sync operation: {op}")

    # Make clean copy
    clean = dict(payload)

    # Strip forbidden diagnostics
    for forbidden_key in ("agent_trace", "timing", "trace", "diagnostics", "debug"):
        clean.pop(forbidden_key, None)

    # Operation-specific payload validation
    if op == "note_put":
        # Required: markdown, updated_at
        return {
            "markdown": str(clean.get("markdown", "")),
            "updated_at": str(clean.get("updated_at") or datetime.now(timezone.utc).isoformat()),
        }
    elif op == "save_patch":
        res: dict[str, Any] = {
            "updated_at": str(clean.get("updated_at") or datetime.now(timezone.utc).isoformat()),
        }
        if "folder_id" in clean:
            res["folder_id"] = clean["folder_id"]
        if "tag_ids" in clean:
            res["tag_ids"] = list(clean["tag_ids"])
        if "user_context" in clean:
            res["user_context"] = clean["user_context"]
        return res
    elif op == "tags_put":
        return {
            "tag_ids": list(clean.get("tag_ids") or []),
            "updated_at": str(clean.get("updated_at") or datetime.now(timezone.utc).isoformat()),
        }
    elif op == "save_create":
        return {
            "url": str(clean.get("url", "")),
            "source_app": str(clean.get("source_app", "other")),
            "user_context": str(clean.get("user_context", "")),
        }
    elif op == "folder_create":
        res = {"name": str(clean.get("name", ""))}
        if "parent_id" in clean:
            res["parent_id"] = clean["parent_id"]
        return res
    elif op == "folder_patch":
        res = {
            "updated_at": str(clean.get("updated_at") or datetime.now(timezone.utc).isoformat()),
        }
        if "name" in clean:
            res["name"] = clean["name"]
        if "parent_id" in clean:
            res["parent_id"] = clean["parent_id"]
        return res
    elif op == "suggestion_accept":
        return {
            "folder_id": clean.get("folder_id"),
            "tag_ids": list(clean.get("tag_ids") or []),
        }

    return clean


def build_sync_push_request(
    ops: list[dict[str, Any]],
    *,
    device_cursor: str | None = None,
) -> dict[str, Any]:
    """Assemble a validated POST /sync/push request body adhering to sync-push.json."""
    sanitized_ops: list[dict[str, Any]] = []
    for item in ops:
        op_name = item.get("op", "")
        raw_payload = item.get("payload", {})
        idempotency_key = item.get("idempotency_key") or str(uuid.uuid4())
        sanitized_payload = sanitize_push_payload(op_name, raw_payload)
        sanitized_ops.append({
            "op": op_name,
            "payload": sanitized_payload,
            "idempotency_key": idempotency_key,
        })

    req: dict[str, Any] = {"ops": sanitized_ops}
    if device_cursor:
        req["device_cursor"] = device_cursor
    return req


class SyncCoordinator:
    """Frontend coordinator managing settings state and sync integration boundaries."""

    def __init__(
        self,
        *,
        device_id: str | None = None,
        initial_cursor: str = "0",
        initial_backup: str | None = None,
        initial_status: str = "Synced",
        initial_settings: dict[str, Any] | None = None,
        on_sync_pull: Callable[[str], dict[str, Any]] | None = None,
        on_sync_push: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        on_persist_settings: Callable[[dict[str, Any]], None] | None = None,
        on_status_change: Callable[[str], None] | None = None,
        on_conflict: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.device_id = device_id or str(uuid.uuid4())
        self.cursor = initial_cursor
        self.last_backup = initial_backup
        self._sync_status = initial_status

        # Settings state initialized with schema defaults
        self._settings = dict(DEFAULT_SETTINGS)
        if initial_settings:
            self._settings.update(initial_settings)
        if "updated_at" not in self._settings:
            self._settings["updated_at"] = datetime.now(timezone.utc).isoformat()

        self.on_sync_pull = on_sync_pull
        self.on_sync_push = on_sync_push
        self.on_persist_settings = on_persist_settings
        self.on_status_change = on_status_change
        self.on_conflict = on_conflict

        self._active_conflict: dict[str, Any] | None = None
        self._is_syncing = False

    @property
    def sync_status(self) -> str:
        """Current status string ('Synced', 'Syncing…', 'Offline', 'Conflict')."""
        return self._sync_status

    @property
    def settings(self) -> dict[str, Any]:
        """Current settings dictionary."""
        return dict(self._settings)

    @property
    def active_conflict(self) -> dict[str, Any] | None:
        """Current active conflict details, if any."""
        return self._active_conflict

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a single setting value."""
        return self._settings.get(key, default)

    def update_setting(self, key: str, value: Any) -> None:
        """Update a setting and notify persistence hook."""
        self._settings[key] = value
        self._settings["updated_at"] = datetime.now(timezone.utc).isoformat()
        if self.on_persist_settings is not None:
            self.on_persist_settings(dict(self._settings))

    def update_settings(self, new_settings: dict[str, Any]) -> None:
        """Bulk update settings."""
        self._settings.update(new_settings)
        self._settings["updated_at"] = datetime.now(timezone.utc).isoformat()
        if self.on_persist_settings is not None:
            self.on_persist_settings(dict(self._settings))

    def set_sync_status(self, status: str) -> None:
        """Update sync status and notify listeners."""
        self._sync_status = status
        if self.on_status_change is not None:
            self.on_status_change(status)

    def trigger_sync(self, pending_ops: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Trigger synchronization cycle (Push offline queue -> Pull latest)."""
        if self._is_syncing:
            return {"status": "in_progress", "sync_status": self._sync_status}

        self._is_syncing = True
        self.set_sync_status("Syncing…")

        try:
            # 1. Replay offline push queue if ops provided
            push_res = {}
            if pending_ops and self.on_sync_push is not None:
                push_req = build_sync_push_request(pending_ops, device_cursor=self.cursor)
                push_res = self.on_sync_push(push_req)

            # 2. Pull server changes since cursor
            pull_res = {}
            if self.on_sync_pull is not None:
                pull_res = self.on_sync_pull(self.cursor)
                new_cursor = pull_res.get("cursor")
                if new_cursor:
                    self.cursor = str(new_cursor)

            # Update last backup timestamp
            self.last_backup = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            self._is_syncing = False
            self.set_sync_status("Synced")
            return {
                "status": "success",
                "sync_status": "Synced",
                "cursor": self.cursor,
                "push": push_res,
                "pull": pull_res,
            }
        except Exception as e:
            self._is_syncing = False
            err_str = str(e).lower()
            if "409" in err_str or "conflict" in err_str:
                self.set_sync_status("Conflict")
                conflict_data = {
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                self._active_conflict = conflict_data
                if self.on_conflict is not None:
                    self.on_conflict(conflict_data)
                return {"status": "conflict", "sync_status": "Conflict", "error": str(e)}
            elif "offline" in err_str or "connection" in err_str or "network" in err_str:
                self.set_sync_status("Offline")
                return {"status": "offline", "sync_status": "Offline", "error": str(e)}
            else:
                self.set_sync_status("Offline")
                return {"status": "error", "sync_status": "Offline", "error": str(e)}

    def register_conflict(
        self,
        save_id: str,
        note_title: str | None = None,
        local_markdown: str | None = None,
        server_updated_at: str | None = None,
    ) -> dict[str, Any]:
        """Register a specific 409 stale-write conflict event."""
        conflict_info = {
            "save_id": save_id,
            "note_title": note_title or "Untitled Note",
            "local_markdown": local_markdown,
            "server_updated_at": server_updated_at,
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
        self._active_conflict = conflict_info
        self.set_sync_status("Conflict")
        if self.on_conflict is not None:
            self.on_conflict(conflict_info)
        return conflict_info

    def clear_conflict(self) -> None:
        """Clear active conflict upon resolution."""
        self._active_conflict = None
        self.set_sync_status("Synced")
