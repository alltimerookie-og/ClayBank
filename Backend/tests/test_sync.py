"""Focused tests for sync pull and push routes."""

from pathlib import Path

from fastapi.testclient import TestClient

from Backend.main import app
from Backend.store.database import Database


HEADERS = {
    "Authorization": "Bearer DEV_TOKEN",
    "X-Device-Id": "test-device",
}


def make_client(tmp_path: Path) -> TestClient:
    """Build a test client with an isolated SQLite database."""
    database = Database(tmp_path / "sync.sqlite3")
    database.initialize()
    app.state.database = database
    return TestClient(app)


def test_sync_pull_returns_changes_and_tombstones(tmp_path: Path) -> None:
    """Pull returns created records and tombstones after the cursor."""
    with make_client(tmp_path) as client:
        save = client.post("/saves", headers=HEADERS, json={"url": "https://example.com/a"}).json()["data"]
        folder = client.post("/folders", headers=HEADERS, json={"name": "Cooking"}).json()["data"]
        client.delete(f"/saves/{save['id']}", headers=HEADERS)
        response = client.get("/sync/pull", params={"since": "0"}, headers=HEADERS)

        assert response.status_code == 200
        data = response.json()["data"]
        assert any(item["id"] == folder["id"] for item in data["folders"])
        assert save["id"] in data["deleted"]
        assert data["cursor"] != "0"


def test_sync_push_replays_offline_writes_idempotently(tmp_path: Path) -> None:
    """Push replays queued operations and repeat keys return the original result."""
    with make_client(tmp_path) as client:
        first = client.post(
            "/sync/push",
            headers=HEADERS,
            json={
                "ops": [
                    {
                        "op": "save_create",
                        "payload": {"url": "https://example.com/offline"},
                        "idempotency_key": "offline-1",
                    }
                ],
                "device_cursor": "0",
            },
        )
        assert first.status_code == 200
        assert first.json()["data"]["results"][0]["ok"] is True
        result_id = first.json()["data"]["results"][0]["result_id"]

        replay = client.post(
            "/sync/push",
            headers=HEADERS,
            json={
                "ops": [
                    {
                        "op": "save_create",
                        "payload": {"url": "https://example.com/offline"},
                        "idempotency_key": "offline-1",
                    }
                ],
                "device_cursor": "0",
            },
        )
        assert replay.json()["data"]["results"][0]["result_id"] == result_id
        saves = client.get("/saves", headers=HEADERS).json()["data"]["items"]
        assert len([item for item in saves if item["id"] == result_id]) == 1


def test_sync_push_reports_conflicts_per_operation(tmp_path: Path) -> None:
    """Stale writes surface as per-operation conflicts without failing the batch."""
    with make_client(tmp_path) as client:
        save = client.post("/saves", headers=HEADERS, json={"url": "https://example.com/a"}).json()["data"]
        response = client.post(
            "/sync/push",
            headers=HEADERS,
            json={
                "ops": [
                    {
                        "op": "note_put",
                        "payload": {
                            "save_id": save["id"],
                            "markdown": "# updated",
                            "updated_at": save["updated_at"],
                        },
                        "idempotency_key": "note-1",
                    },
                    {
                        "op": "save_patch",
                        "payload": {"save_id": save["id"], "updated_at": save["updated_at"]},
                        "idempotency_key": "stale-1",
                    },
                ],
                "device_cursor": "0",
            },
        )

        assert response.status_code == 200
        results = response.json()["data"]["results"]
        assert results[0]["ok"] is True
        assert results[1]["ok"] is False
        assert results[1]["error"]["code"] == "conflict"
