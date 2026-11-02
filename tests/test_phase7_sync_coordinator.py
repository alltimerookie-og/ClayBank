"""Tests for SyncCoordinator and client payload hygiene (P7-06 deliverable).

Validates in-memory settings defaults, status transitions, manual sync dispatch,
payload sanitization ensuring agent_trace exclusion per ADR 0002, 409 conflict
propagation, and offline resilience.
"""

from __future__ import annotations

import pytest

from app.views.sync.sync_coordinator import (
    ALLOWED_OPS,
    DEFAULT_SETTINGS,
    SyncCoordinator,
    build_sync_push_request,
    sanitize_push_payload,
)


class TestSyncCoordinator:
    """Test suite for SyncCoordinator and payload hygiene utilities."""

    def test_default_settings_schema(self) -> None:
        """Verify defaults matching Docs/db/0003_device.sql."""
        coord = SyncCoordinator()
        assert coord.settings["chat_model"] == "cloud"
        assert coord.settings["local_model_id"] == "minicpm5-2b"
        assert coord.settings["auto_sort"] is True
        assert coord.settings["weekly_digest"] is True
        assert coord.settings["wifi_only_processing"] is False
        assert coord.settings["quick_save_notification"] is True
        assert "updated_at" in coord.settings

    def test_setting_updates_and_persistence_hook(self) -> None:
        """Verify updating a setting notifies on_persist_settings callback."""
        persisted: list[dict] = []

        coord = SyncCoordinator(on_persist_settings=lambda s: persisted.append(s))
        coord.update_setting("chat_model", "local")

        assert coord.get_setting("chat_model") == "local"
        assert len(persisted) == 1
        assert persisted[0]["chat_model"] == "local"

    def test_client_payload_hygiene_agent_trace_exclusion(self) -> None:
        """ADR 0002 / Rules.md §5: agent_trace and diagnostics are stripped from push ops."""
        raw_note_payload = {
            "markdown": "# Important Research Note",
            "updated_at": "2026-10-31T12:00:00Z",
            "agent_trace": {
                "decision": "high_confidence",
                "steps": ["extract", "transcribe"],
            },
            "timing": {"extracting": 3100},
            "diagnostics": "internal_error_log",
        }

        sanitized = sanitize_push_payload("note_put", raw_note_payload)
        assert "agent_trace" not in sanitized
        assert "timing" not in sanitized
        assert "diagnostics" not in sanitized
        assert sanitized["markdown"] == "# Important Research Note"
        assert sanitized["updated_at"] == "2026-10-31T12:00:00Z"

    def test_sanitize_all_allowed_ops(self) -> None:
        """Verify sanitization across allowed ops."""
        # save_patch
        p1 = sanitize_push_payload("save_patch", {"folder_id": "f-1", "agent_trace": "forbidden"})
        assert "agent_trace" not in p1
        assert p1["folder_id"] == "f-1"

        # tags_put
        p2 = sanitize_push_payload("tags_put", {"tag_ids": ["t-1", "t-2"], "debug": True})
        assert "debug" not in p2
        assert p2["tag_ids"] == ["t-1", "t-2"]

        # folder_create
        p3 = sanitize_push_payload("folder_create", {"name": "Recipes", "timing": 120})
        assert "timing" not in p3
        assert p3["name"] == "Recipes"

        # Invalid op
        with pytest.raises(ValueError):
            sanitize_push_payload("unknown_op", {})

    def test_build_sync_push_request(self) -> None:
        """Verify assembly of POST /sync/push request matching schema."""
        raw_ops = [
            {
                "op": "note_put",
                "payload": {"markdown": "Hello", "agent_trace": "ignore"},
                "idempotency_key": "idempotent-key-01",
            }
        ]
        req = build_sync_push_request(raw_ops, device_cursor="c-00042")
        assert req["device_cursor"] == "c-00042"
        assert len(req["ops"]) == 1
        assert req["ops"][0]["op"] == "note_put"
        assert req["ops"][0]["idempotency_key"] == "idempotent-key-01"
        assert "agent_trace" not in req["ops"][0]["payload"]

    def test_sync_cycle_success(self) -> None:
        """Successful sync cycle calls push then pull and updates cursor/backup timestamp."""
        pull_calls: list[str] = []
        push_calls: list[dict] = []

        def mock_pull(cursor: str) -> dict:
            pull_calls.append(cursor)
            return {"saves": [], "notes": [], "folders": [], "jobs": [], "deleted": [], "cursor": "c-00043"}

        def mock_push(req: dict) -> dict:
            push_calls.append(req)
            return {"status": "ok"}

        coord = SyncCoordinator(
            initial_cursor="c-00042",
            on_sync_pull=mock_pull,
            on_sync_push=mock_push,
        )

        ops = [{"op": "folder_create", "payload": {"name": "Test"}}]
        res = coord.trigger_sync(pending_ops=ops)

        assert res["status"] == "success"
        assert coord.sync_status == "Synced"
        assert coord.cursor == "c-00043"
        assert coord.last_backup is not None
        assert len(push_calls) == 1
        assert len(pull_calls) == 1

    def test_sync_cycle_409_conflict(self) -> None:
        """409 conflict during sync transitions to Conflict status and invokes on_conflict."""
        conflicts: list[dict] = []

        def failing_push(req: dict) -> dict:
            raise RuntimeError("409 Conflict: stale write on note-001")

        coord = SyncCoordinator(
            on_sync_push=failing_push,
            on_conflict=lambda c: conflicts.append(c),
        )

        ops = [{"op": "note_put", "payload": {"markdown": "edit"}}]
        res = coord.trigger_sync(pending_ops=ops)

        assert res["status"] == "conflict"
        assert coord.sync_status == "Conflict"
        assert len(conflicts) == 1
        assert coord.active_conflict is not None

    def test_register_and_clear_conflict(self) -> None:
        """Verify manual registration and clearance of conflict."""
        coord = SyncCoordinator()
        assert coord.sync_status == "Synced"

        coord.register_conflict("save-01", "Chicken Soup", "# Local Edit", "2026-10-31T12:00:00Z")
        assert coord.sync_status == "Conflict"
        assert coord.active_conflict["save_id"] == "save-01"

        coord.clear_conflict()
        assert coord.sync_status == "Synced"
        assert coord.active_conflict is None

    def test_sync_cycle_offline_failure(self) -> None:
        """Network failure transitions to Offline status."""
        def failing_pull(cursor: str) -> dict:
            raise ConnectionError("Network offline")

        coord = SyncCoordinator(on_sync_pull=failing_pull)
        res = coord.trigger_sync()

        assert res["status"] == "offline"
        assert coord.sync_status == "Offline"
